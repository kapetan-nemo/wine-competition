from django.test import TestCase, Client, RequestFactory
from django.contrib.auth.models import User
from django.urls import reverse
from wine_app.models import Competition, Wine, Round, Pairing, Vote
from wine_app.views import create_pairings, end_round
from django.contrib.messages.storage.fallback import FallbackStorage
import datetime


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_request(factory, user, path='/'):
    """Create a POST request with message middleware attached."""
    req = factory.post(path)
    req.user = user
    setattr(req, 'session', 'session')
    msgs = FallbackStorage(req)
    setattr(req, '_messages', msgs)
    return req


# ---------------------------------------------------------------------------
# Bracket / Round workflow tests
# ---------------------------------------------------------------------------

class TournamentWorkflowTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="testadmin", password="password")
        self.comp = Competition.objects.create(
            title="Test Comp",
            date=datetime.date.today(),
            organizer=self.user,
            status="running"
        )
        self.wine_a = Wine.objects.create(competition=self.comp, name="Wine A", country="FR", order=1)
        self.wine_b = Wine.objects.create(competition=self.comp, name="Wine B", country="IT", order=2)
        self.wine_c = Wine.objects.create(competition=self.comp, name="Wine C", country="SP", order=3)
        self.wine_d = Wine.objects.create(competition=self.comp, name="Wine D", country="US", order=4)
        self.r1 = Round.objects.create(competition=self.comp, round_number=1, status="active")
        self.factory = RequestFactory()

    def test_end_round_preserves_winners_and_bracket(self):
        pairings = create_pairings(self.r1)
        self.assertEqual(len(pairings), 2)

        p0, p1 = pairings[0], pairings[1]

        p0_winner = p0.wine1
        p0.votes_wine1 = 5
        p0.votes_wine2 = 5
        p0.status = "completed"
        p0.winner = p0_winner
        p0.save()

        p1_winner = p1.wine2
        p1.votes_wine1 = 2
        p1.votes_wine2 = 6
        p1.status = "completed"
        p1.winner = p1_winner
        p1.save()

        end_round(_make_request(self.factory, self.user), self.comp.id, self.r1.id)

        p0.refresh_from_db()
        self.assertEqual(p0.winner, p0_winner)

        r2 = self.comp.rounds.get(round_number=2)
        r2_pairings = r2.pairings.all()
        self.assertEqual(len(r2_pairings), 1)

        r2_wine_set = {r2_pairings[0].wine1, r2_pairings[0].wine2}
        self.assertIn(p0_winner, r2_wine_set)
        self.assertIn(p1_winner, r2_wine_set)


# ---------------------------------------------------------------------------
# create_pairings Bye-bracket algorithm tests
# ---------------------------------------------------------------------------

class CreatePairingsTest(TestCase):
    """Tests for the Bye-bracket algorithm in create_pairings()."""

    def setUp(self):
        self.user = User.objects.create_user(username="admin2", password="pass")
        self.comp = Competition.objects.create(
            title="Bracket Test", date=datetime.date.today(),
            organizer=self.user, status="running"
        )

    def _make_wines(self, count):
        return [
            Wine.objects.create(competition=self.comp, name=f"Wine {i}", country="FR", order=i)
            for i in range(1, count + 1)
        ]

    def _make_round(self, number):
        return Round.objects.create(competition=self.comp, round_number=number, status="active")

    def test_4_wines_no_byes(self):
        self._make_wines(4)
        r = self._make_round(1)
        pairings = create_pairings(r)
        self.assertEqual(len(pairings), 2)
        self.assertTrue(all(p.wine2 is not None for p in pairings))
        self.assertTrue(all(p.status == "pending" for p in pairings))

    def test_3_wines_creates_one_bye(self):
        """3 wines → next power of 2 is 4 → 1 bye, 1 real pairing."""
        self._make_wines(3)
        r = self._make_round(1)
        pairings = create_pairings(r)
        self.assertEqual(len(pairings), 2)  # 1 real + 1 bye
        byes = [p for p in pairings if p.wine2 is None]
        real = [p for p in pairings if p.wine2 is not None]
        self.assertEqual(len(real), 1)
        self.assertEqual(len(byes), 1)
        self.assertEqual(byes[0].status, "completed")
        self.assertEqual(byes[0].winner, byes[0].wine1)
        self.assertEqual(real[0].status, "pending")

    def test_5_wines_creates_three_byes(self):
        """5 wines → next power of 2 is 8 → 3 byes, 1 real pairing."""
        self._make_wines(5)
        r = self._make_round(1)
        pairings = create_pairings(r)
        self.assertEqual(len(pairings), 4)  # 1 real + 3 byes
        byes = [p for p in pairings if p.wine2 is None]
        real = [p for p in pairings if p.wine2 is not None]
        self.assertEqual(len(byes), 3)
        self.assertEqual(len(real), 1)

    def test_7_wines_creates_one_bye(self):
        """7 wines → next power of 2 is 8 → 1 bye, 3 real pairings."""
        self._make_wines(7)
        r = self._make_round(1)
        pairings = create_pairings(r)
        self.assertEqual(len(pairings), 4)
        byes = [p for p in pairings if p.wine2 is None]
        real = [p for p in pairings if p.wine2 is not None]
        self.assertEqual(len(byes), 1)
        self.assertEqual(len(real), 3)

    def test_2_wines_no_byes(self):
        """2 wines → exactly 1 real pairing, no byes."""
        self._make_wines(2)
        r = self._make_round(1)
        pairings = create_pairings(r)
        self.assertEqual(len(pairings), 1)
        self.assertIsNotNone(pairings[0].wine2)
        self.assertEqual(pairings[0].status, "pending")

    def test_empty_wines_returns_empty_list(self):
        """No wines → create_pairings logs error and returns []."""
        r = self._make_round(1)
        pairings = create_pairings(r)
        self.assertEqual(pairings, [])


# ---------------------------------------------------------------------------
# vote() view tests
# ---------------------------------------------------------------------------

VALID_UUID = "550e8400-e29b-41d4-a716-446655440000"


class VoteViewTest(TestCase):

    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(username="organizer", password="pass")
        self.comp = Competition.objects.create(
            title="Vote Test", date=datetime.date.today(),
            organizer=self.user, status="running"
        )
        self.wine1 = Wine.objects.create(competition=self.comp, name="Red", country="FR", order=1)
        self.wine2 = Wine.objects.create(competition=self.comp, name="White", country="IT", order=2)
        self.r1 = Round.objects.create(competition=self.comp, round_number=1, status="active")
        self.pairing = Pairing.objects.create(
            round=self.r1, wine1=self.wine1, wine2=self.wine2,
            status="active", order=0
        )

    def _vote(self, wine_id, cookie_id=VALID_UUID):
        self.client.cookies['wine_competition_id'] = cookie_id
        url = reverse('vote', args=[self.pairing.id])
        return self.client.post(url, {'wine_id': wine_id})

    def test_vote_success(self):
        resp = self._vote(self.wine1.id)
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertTrue(data['success'])
        self.assertEqual(data['votes_wine1'], 1)
        self.assertEqual(data['votes_wine2'], 0)

    def test_vote_updates_db(self):
        self._vote(self.wine1.id)
        self.pairing.refresh_from_db()
        self.assertEqual(self.pairing.votes_wine1, 1)
        self.assertEqual(self.pairing.votes_wine2, 0)
        self.assertEqual(Vote.objects.count(), 1)

    def test_vote_change_switches_counts(self):
        """Voting wine1 then wine2 switches the counts atomically."""
        self._vote(self.wine1.id)
        self._vote(self.wine2.id)
        self.pairing.refresh_from_db()
        self.assertEqual(self.pairing.votes_wine1, 0)
        self.assertEqual(self.pairing.votes_wine2, 1)
        self.assertEqual(Vote.objects.count(), 1)  # still 1 vote, just changed

    def test_vote_same_wine_is_idempotent(self):
        """Voting for same wine twice must not double-count."""
        self._vote(self.wine1.id)
        resp = self._vote(self.wine1.id)
        data = resp.json()
        self.assertFalse(data['changed'])
        self.pairing.refresh_from_db()
        self.assertEqual(self.pairing.votes_wine1, 1)

    def test_vote_without_cookie_returns_400(self):
        url = reverse('vote', args=[self.pairing.id])
        resp = self.client.post(url, {'wine_id': self.wine1.id})
        self.assertEqual(resp.status_code, 400)
        self.assertIn('error', resp.json())

    def test_vote_with_invalid_cookie_format_returns_400(self):
        self.client.cookies['wine_competition_id'] = 'not-a-valid-uuid'
        url = reverse('vote', args=[self.pairing.id])
        resp = self.client.post(url, {'wine_id': self.wine1.id})
        self.assertEqual(resp.status_code, 400)
        self.assertIn('Invalid voter identifier', resp.json()['error'])

    def test_vote_against_completed_pairing_returns_400(self):
        self.pairing.status = "completed"
        self.pairing.save()
        resp = self._vote(self.wine1.id)
        self.assertEqual(resp.status_code, 400)

    def test_vote_against_pending_pairing_returns_400(self):
        self.pairing.status = "pending"
        self.pairing.save()
        resp = self._vote(self.wine1.id)
        self.assertEqual(resp.status_code, 400)


# ---------------------------------------------------------------------------
# Auth views tests
# ---------------------------------------------------------------------------

class AuthViewsTest(TestCase):

    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(username="testuser", password="testpass123")

    def test_logout_rejects_get_request(self):
        """GET /logout/ must not log the user out (require_POST protection)."""
        self.client.login(username="testuser", password="testpass123")
        resp = self.client.get(reverse('logout'))
        # Django's require_POST returns 405 Method Not Allowed
        self.assertEqual(resp.status_code, 405)
        # Session should still have the user
        self.assertIn('_auth_user_id', self.client.session)

    def test_logout_post_works(self):
        self.client.login(username="testuser", password="testpass123")
        resp = self.client.post(reverse('logout'))
        self.assertRedirects(resp, reverse('home'))
        self.assertNotIn('_auth_user_id', self.client.session)

    def test_competition_detail_blocked_for_non_owner(self):
        """A user cannot access another user's competition detail."""
        other = User.objects.create_user(username="other", password="pass")
        comp = Competition.objects.create(
            title="Other's comp", date=datetime.date.today(),
            organizer=other, status="draft"
        )
        self.client.login(username="testuser", password="testpass123")
        resp = self.client.get(reverse('competition_detail', args=[comp.id]))
        self.assertEqual(resp.status_code, 404)

    def test_anonymous_cannot_create_competition(self):
        resp = self.client.get(reverse('competition_create'))
        self.assertRedirects(resp, f"/login/?next={reverse('competition_create')}")

    def test_start_competition_requires_min_2_wines(self):
        self.client.login(username="testuser", password="testpass123")
        comp = Competition.objects.create(
            title="Solo comp", date=datetime.date.today(),
            organizer=self.user, status="draft"
        )
        Wine.objects.create(competition=comp, name="Lone Wine", country="FR", order=1)
        resp = self.client.post(reverse('start_competition', args=[comp.id]))
        comp.refresh_from_db()
        self.assertEqual(comp.status, "draft")  # must stay draft

    def test_start_competition_is_atomic_on_double_post(self):
        """Second start_competition POST must not create a second Round 1."""
        self.client.login(username="testuser", password="testpass123")
        comp = Competition.objects.create(
            title="Double Start", date=datetime.date.today(),
            organizer=self.user, status="draft"
        )
        Wine.objects.create(competition=comp, name="Wine A", country="FR", order=1)
        Wine.objects.create(competition=comp, name="Wine B", country="IT", order=2)

        self.client.post(reverse('start_competition', args=[comp.id]))
        # Simulate second POST (double-click scenario)
        self.client.post(reverse('start_competition', args=[comp.id]))

        comp.refresh_from_db()
        self.assertEqual(comp.status, "running")
        # Only one Round #1 must exist
        self.assertEqual(Round.objects.filter(competition=comp, round_number=1).count(), 1)
