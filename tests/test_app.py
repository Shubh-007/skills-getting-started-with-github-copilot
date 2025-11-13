"""
Tests for the Mergington High School Activities API
"""

import pytest
from fastapi.testclient import TestClient
import sys
from pathlib import Path

# Add src directory to path to import app
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from app import app, activities


@pytest.fixture
def client():
    """Create a test client for the FastAPI app"""
    return TestClient(app)


@pytest.fixture
def reset_activities():
    """Reset activities to initial state before each test"""
    # Store original state
    original_activities = {
        name: {
            "description": details["description"],
            "schedule": details["schedule"],
            "max_participants": details["max_participants"],
            "participants": details["participants"].copy()
        }
        for name, details in activities.items()
    }
    
    yield
    
    # Restore original state after test
    for name in activities:
        activities[name]["participants"] = original_activities[name]["participants"].copy()


class TestGetActivities:
    """Tests for GET /activities endpoint"""
    
    def test_get_all_activities(self, client):
        """Test retrieving all activities"""
        response = client.get("/activities")
        assert response.status_code == 200
        data = response.json()
        
        # Check that all activities are returned
        assert "Chess Club" in data
        assert "Programming Class" in data
        assert "Gym Class" in data
        
        # Check activity structure
        chess_club = data["Chess Club"]
        assert "description" in chess_club
        assert "schedule" in chess_club
        assert "max_participants" in chess_club
        assert "participants" in chess_club
        assert isinstance(chess_club["participants"], list)
    
    def test_get_activities_has_participants(self, client):
        """Test that activities have initial participants"""
        response = client.get("/activities")
        data = response.json()
        
        chess_club = data["Chess Club"]
        assert len(chess_club["participants"]) > 0
        assert "michael@mergington.edu" in chess_club["participants"]


class TestGetActivityByName:
    """Tests for GET /activities/{activity_name} endpoint"""
    
    def test_get_specific_activity(self, client):
        """Test retrieving a specific activity"""
        response = client.get("/activities/Chess%20Club")
        assert response.status_code == 200
        data = response.json()
        
        assert "Chess Club" in data
        assert data["Chess Club"]["description"] == "Learn strategies and compete in chess tournaments"
    
    def test_get_nonexistent_activity(self, client):
        """Test retrieving an activity that doesn't exist"""
        response = client.get("/activities/NonexistentClub")
        assert response.status_code == 404
        assert response.json()["detail"] == "Activity not found"
    
    def test_get_activity_with_special_characters(self, client):
        """Test retrieving activities with spaces in names"""
        response = client.get("/activities/Basketball%20Team")
        assert response.status_code == 200
        data = response.json()
        assert "Basketball Team" in data


class TestSignupForActivity:
    """Tests for POST /activities/{activity_name}/signup endpoint"""
    
    def test_successful_signup(self, client, reset_activities):
        """Test successful signup for an activity"""
        response = client.post(
            "/activities/Chess%20Club/signup?email=newstudent@mergington.edu"
        )
        assert response.status_code == 200
        data = response.json()
        assert "Signed up" in data["message"]
        
        # Verify participant was added
        activities_response = client.get("/activities")
        activities_data = activities_response.json()
        assert "newstudent@mergington.edu" in activities_data["Chess Club"]["participants"]
    
    def test_signup_nonexistent_activity(self, client, reset_activities):
        """Test signup for an activity that doesn't exist"""
        response = client.post(
            "/activities/NonexistentClub/signup?email=student@mergington.edu"
        )
        assert response.status_code == 404
        assert response.json()["detail"] == "Activity not found"
    
    def test_signup_already_registered(self, client, reset_activities):
        """Test signup for activity when already registered"""
        response = client.post(
            "/activities/Chess%20Club/signup?email=michael@mergington.edu"
        )
        assert response.status_code == 400
        assert "already signed up" in response.json()["detail"]
    
    def test_signup_activity_full(self, client, reset_activities):
        """Test signup for an activity that is full"""
        # Get an activity and fill it up
        activity = activities["Basketball Team"]
        original_max = activity["max_participants"]
        
        # Temporarily set capacity to current participant count
        activity["max_participants"] = len(activity["participants"])
        
        response = client.post(
            "/activities/Basketball%20Team/signup?email=newstudent@mergington.edu"
        )
        assert response.status_code == 400
        assert "Activity is full" in response.json()["detail"]
        
        # Restore original capacity
        activity["max_participants"] = original_max
    
    def test_signup_multiple_activities(self, client, reset_activities):
        """Test signing up for multiple activities"""
        email = "versatile@mergington.edu"
        
        # Sign up for Chess Club
        response1 = client.post(f"/activities/Chess%20Club/signup?email={email}")
        assert response1.status_code == 200
        
        # Sign up for Programming Class
        response2 = client.post(f"/activities/Programming%20Class/signup?email={email}")
        assert response2.status_code == 200
        
        # Verify student is in both activities
        activities_response = client.get("/activities")
        data = activities_response.json()
        assert email in data["Chess Club"]["participants"]
        assert email in data["Programming Class"]["participants"]


class TestRemoveParticipant:
    """Tests for DELETE /activities/{activity_name}/participants/{email} endpoint"""
    
    def test_remove_participant(self, client, reset_activities):
        """Test removing a participant from an activity"""
        # First verify participant exists
        response = client.get("/activities")
        data = response.json()
        original_count = len(data["Chess Club"]["participants"])
        assert "michael@mergington.edu" in data["Chess Club"]["participants"]
        
        # Remove participant
        delete_response = client.delete(
            "/activities/Chess%20Club/participants/michael@mergington.edu"
        )
        assert delete_response.status_code == 200
        assert "Removed" in delete_response.json()["message"]
        
        # Verify participant was removed
        check_response = client.get("/activities")
        check_data = check_response.json()
        assert "michael@mergington.edu" not in check_data["Chess Club"]["participants"]
        assert len(check_data["Chess Club"]["participants"]) == original_count - 1
    
    def test_remove_nonexistent_participant(self, client, reset_activities):
        """Test removing a participant that doesn't exist"""
        response = client.delete(
            "/activities/Chess%20Club/participants/nonexistent@mergington.edu"
        )
        assert response.status_code == 404
        assert "Participant not found" in response.json()["detail"]
    
    def test_remove_from_nonexistent_activity(self, client, reset_activities):
        """Test removing from an activity that doesn't exist"""
        response = client.delete(
            "/activities/NonexistentClub/participants/student@mergington.edu"
        )
        assert response.status_code == 404
        assert "Activity not found" in response.json()["detail"]
    
    def test_remove_and_readd_participant(self, client, reset_activities):
        """Test removing and re-adding a participant"""
        email = "michael@mergington.edu"
        
        # Remove participant
        delete_response = client.delete(f"/activities/Chess%20Club/participants/{email}")
        assert delete_response.status_code == 200
        
        # Verify removed
        check1 = client.get("/activities")
        assert email not in check1.json()["Chess Club"]["participants"]
        
        # Re-add participant
        signup_response = client.post(f"/activities/Chess%20Club/signup?email={email}")
        assert signup_response.status_code == 200
        
        # Verify re-added
        check2 = client.get("/activities")
        assert email in check2.json()["Chess Club"]["participants"]


class TestRootEndpoint:
    """Tests for GET / endpoint"""
    
    def test_root_redirect(self, client):
        """Test that root redirects to index.html"""
        response = client.get("/", follow_redirects=False)
        assert response.status_code == 307
        assert response.headers["location"] == "/static/index.html"
