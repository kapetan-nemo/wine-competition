import sys
import datetime
from django.contrib.auth.models import User
from wine_app.models import Competition, Wine, Round, Pairing, Vote
from wine_app.views import create_pairings
from django.http import HttpRequest
from django.contrib.messages.storage.fallback import FallbackStorage

def run():
    print("--- STARTING TEST ---")
    User.objects.filter(username="testadmin").delete()
    user = User.objects.create_superuser("testadmin", "admin@example.com", "pass")
    
    comp = Competition.objects.create(
        title="Test Comp", 
        date=datetime.date.today(), 
        organizer=user,
        status="running"
    )
    
    # Add 4 wines (even number, standard bracket)
    w1 = Wine.objects.create(competition=comp, name="Wine A", country="FR", order=1)
    w2 = Wine.objects.create(competition=comp, name="Wine B", country="IT", order=2)
    w3 = Wine.objects.create(competition=comp, name="Wine C", country="SP", order=3)
    w4 = Wine.objects.create(competition=comp, name="Wine D", country="US", order=4)
    
    r1 = Round.objects.create(competition=comp, round_number=1, status="active")
    pairings = create_pairings(r1)
    
    print("\nRound 1 Pairings:")
    for p in pairings:
        w2_name = p.wine2.name if p.wine2 else "None"
        print(f" [{p.order}] {p.wine1.name} vs {w2_name}")
        
    # Set winners: W1 and W3
    p0 = pairings[0]
    p1 = pairings[1]
    
    # Tie for p0, manual winner W1
    p0.votes_wine1 = 5
    p0.votes_wine2 = 5
    p0.status = "completed"
    p0.winner = w1
    p0.save()
    
    # W3 beats W4 for p1
    p1.votes_wine1 = 6
    p1.votes_wine2 = 2
    p1.status = "completed"
    p1.winner = p1.wine1 # W3
    p1.save()
    
    req = HttpRequest()
    req.user = user
    setattr(req, 'session', 'session')
    messages = FallbackStorage(req)
    setattr(req, '_messages', messages)
    
    from wine_app.views import end_round
    print("\nRunning end_round()...")
    # This will generate Round 2
    end_round(req, comp.id, r1.id)
    
    p0.refresh_from_db()
    
    if p0.winner != w1:
         print("BUG DETECTED! end_round overwrote the winner for pairing 0!")
    else:
         print("Winner for pairing 0 remained intact.")
         
    r2 = comp.rounds.get(round_number=2)
    r2_pairings = create_pairings(r2) # Actually create_pairings was already called inside end_round, let's fetch them
    
    # Delete r2 pairings and re-run create_pairings 10 times to check if it's shuffling
    print("\nTesting bracket shuffle... (Running create_pairings multiple times for Round 2)")
    shuffle_detected = False
    
    first_wine_seen = None
    for _ in range(10):
        r2.pairings.all().delete()
        test_pairs = create_pairings(r2)
        top_seed = test_pairs[0].wine1.name
        if first_wine_seen is None:
            first_wine_seen = top_seed
        elif first_wine_seen != top_seed:
            shuffle_detected = True
            break
            
    if shuffle_detected:
        print("BUG DETECTED! create_pairings is shuffling the bracket randomly in Round 2!")
    else:
        print("No shuffle detected.")
        
    print("\n--- TEST COMPLETE ---")

run()
