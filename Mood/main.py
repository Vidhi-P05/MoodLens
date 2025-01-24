import os
import requests
import spotipy
from spotipy.oauth2 import SpotifyClientCredentials
from flask import Flask, render_template, request, redirect, url_for, session, jsonify
from googleapiclient.discovery import build
import cv2
import numpy as np
import tensorflow as tf
import bcrypt
import mysql.connector
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from werkzeug.utils import secure_filename

# Initialize Flask app
app = Flask(__name__)

# Load the emotion detection model
# model = tf.keras.models.load_model('emotion_model.h5')  # Replace with your model path

# Emotion labels
emotion_labels = ['Angry', 'Happy', 'Sad', 'Surprise', 'Neutral']

# Configure MySQL Database
app.config['SECRET_KEY'] = 'mysecretkey'  # Secret key for sessions

db_config = {
    'host': 'localhost',
    'user': 'root',  # Replace with your MySQL username
    'password': 'password',  # Replace with your MySQL password
    'database': 'Database_Namw',
    'auth_plugin': 'mysql_native_password'
}

# Initialize Login Manager
login_manager = LoginManager(app)
login_manager.login_view = "login"

# User model class for flask-login
class User(UserMixin):
    def __init__(self, user_id, username, email):
        self.id = user_id
        self.username = username
        self.email = email

# Load user function for flask-login
@login_manager.user_loader
def load_user(user_id):
    connection = mysql.connector.connect(**db_config)
    cursor = connection.cursor(dictionary=True)

    cursor.execute("SELECT * FROM users WHERE id = %s", (user_id,))
    user = cursor.fetchone()
    connection.close()

    if user:
        return User(user['id'], user['username'], user['email'])
    return None

# Index route
@app.route('/')
def index():
    return render_template('index.html')

# Login route
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']

        connection = mysql.connector.connect(**db_config)
        cursor = connection.cursor(dictionary=True)

        # Check if user exists in MySQL
        cursor.execute("SELECT * FROM users WHERE email = %s", (email,))
        user = cursor.fetchone()

        connection.close()

        if user and bcrypt.checkpw(password.encode('utf-8'), user['password'].encode('utf-8')):
            # User authenticated, log them in
            user_obj = User(user['id'], user['username'], user['email'])
            login_user(user_obj)
            return redirect(url_for('home'))
        else:
            return 'Invalid email or password', 401

    return render_template('login.html')

# Signup route
@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        username = request.form['username']
        email = request.form['email']
        password = request.form['password']
        confirm_password = request.form['confirm-password']

        # Check if the passwords match
        if password != confirm_password:
            return 'Passwords do not match', 400

        connection = mysql.connector.connect(**db_config)
        cursor = connection.cursor()

        # Check if the user already exists
        cursor.execute("SELECT * FROM users WHERE email = %s", (email,))
        if cursor.fetchone():
            connection.close()
            return 'Email already exists', 400

        # Hash the password
        hashed_password = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt())

        # Create a new user in MySQL
        cursor.execute("INSERT INTO users (username, email, password) VALUES (%s, %s, %s)",
                       (username, email, hashed_password.decode('utf-8')))
        connection.commit()

        user_id = cursor.lastrowid
        connection.close()

        # Log the user in
        new_user = User(user_id, username, email)
        login_user(new_user)

        return redirect(url_for('login'))

    return render_template('signup.html')

# Logout route
@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('index'))

# Spotify API Configuration
CLIENT_ID = "Spotify_Key"
CLIENT_SECRET = "Client_Secret"
sp = spotipy.Spotify(auth_manager=SpotifyClientCredentials(client_id=CLIENT_ID, client_secret=CLIENT_SECRET))

# YouTube API Configuration
YOUTUBE_API_KEY = 'Youtube_API_Key'
youtube = build('youtube', 'v3', developerKey=YOUTUBE_API_KEY)

# Function to detect emotion from the image
def detect_emotion(image_path):
    img = cv2.imread(image_path)
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    face_cascade = cv2.CascadeClassifier(cv2.data.haarcascades + 'haarcascade_frontalface_default.xml')
    faces = face_cascade.detectMultiScale(gray, 1.3, 5)

    if len(faces) == 0:
        return "No face detected"

    for (x, y, w, h) in faces:
        face = gray[y:y + h, x:x + w]
        face_resized = cv2.resize(face, (48, 48))
        face_normalized = face_resized / 255.0
        face_expanded = np.expand_dims(face_normalized, axis=0)
        face_expanded = np.expand_dims(face_expanded, axis=-1)

        emotion = model.predict(face_expanded)
        emotion_index = np.argmax(emotion)
        return emotion_labels[emotion_index]

# Function to save Spotify preferences (for instance, top genres or artists)
def save_spotify_preferences(user_id, genre, artist):
    connection = mysql.connector.connect(**db_config)
    cursor = connection.cursor()
    cursor.execute("INSERT INTO user_preferences (user_id, genre, artist) VALUES (%s, %s, %s)",
                   (user_id, genre, artist))
    connection.commit()
    connection.close()

# Function to save YouTube video history
def save_youtube_history(user_id, video_id):
    connection = mysql.connector.connect(**db_config)
    cursor = connection.cursor()
    cursor.execute("INSERT INTO user_youtube_history (user_id, video_id, watched_at) VALUES (%s, %s, NOW())",
                   (user_id, video_id))
    connection.commit()
    connection.close()

# Function to save Instagram hashtag interactions
def save_instagram_hashtags(user_id, hashtag):
    connection = mysql.connector.connect(**db_config)
    cursor = connection.cursor()
    cursor.execute("INSERT INTO user_hashtags (user_id, hashtag) VALUES (%s, %s)",
                   (user_id, hashtag))
    connection.commit()
    connection.close()

# Function to save mood detected from user image
def save_user_mood(user_id, mood):
    connection = mysql.connector.connect(**db_config)
    cursor = connection.cursor()
    cursor.execute("INSERT INTO user_moods (user_id, detected_mood, detected_at) VALUES (%s, %s, NOW())",
                   (user_id, mood))
    connection.commit()
    connection.close()

# Fetch user preferences (Spotify artists/genres)
def get_user_preferences(user_id):
    connection = mysql.connector.connect(**db_config)
    cursor = connection.cursor(dictionary=True)
    cursor.execute("SELECT genre, artist FROM user_preferences WHERE user_id = %s", (user_id,))
    preferences = cursor.fetchall()
    connection.close()
    return preferences

# Fetch user mood (most recent mood)
def get_user_mood(user_id):
    connection = mysql.connector.connect(**db_config)
    cursor = connection.cursor(dictionary=True)
    cursor.execute("SELECT detected_mood FROM user_moods WHERE user_id = %s ORDER BY detected_at DESC LIMIT 1",
                   (user_id,))
    mood_data = cursor.fetchone()
    connection.close()
    return mood_data['detected_mood'] if mood_data else 'Neutral'

# Fetch YouTube history (watched videos)
def get_youtube_history(user_id):
    connection = mysql.connector.connect(**db_config)
    cursor = connection.cursor(dictionary=True)
    cursor.execute("SELECT video_id FROM user_youtube_history WHERE user_id = %s", (user_id,))
    watched_videos = [row['video_id'] for row in cursor.fetchall()]
    connection.close()
    return watched_videos

# Fetch Instagram hashtags (user interactions)
def get_instagram_hashtags(user_id):
    connection = mysql.connector.connect(**db_config)
    cursor = connection.cursor(dictionary=True)
    cursor.execute("SELECT hashtag FROM user_hashtags WHERE user_id = %s", (user_id,))
    hashtags = [row['hashtag'] for row in cursor.fetchall()]
    connection.close()
    return hashtags


def get_spotify_recommendations(user_id, mood):
    preferences = get_user_preferences(user_id)  # Fetch user preferences

    # Define mood-genre mapping
    mood_genre_mapping = {
        'Happy': ['happy', 'dance', 'upbeat', 'feel-good', 'party', 'summer'],
        'Sad': ['sad', 'melancholic', 'ballads', 'slow', 'soul', 'heartbreak'],
        'Angry': ['metal', 'hard rock', 'grunge', 'punk', 'hip-hop', 'intense'],
        'Surprise': ['electro', 'intense', 'high energy', 'dubstep', 'trap'],
        'Neutral': ['chill', 'ambient', 'lo-fi', 'classical', 'relax', 'focus']
    }

    # Build search query based on mood
    search_query = "chill music"  # Default query
    if mood in mood_genre_mapping:
        search_query = " OR ".join(mood_genre_mapping[mood])

    # Add user preferences to the query
    if preferences:
        preferred_genres = [pref.get('genre', '') for pref in preferences if 'genre' in pref]
        preferred_artists = [pref.get('artist', '') for pref in preferences if 'artist' in pref]
        search_query += " OR " + " OR ".join(preferred_genres + preferred_artists)

    try:
        # Call Spotify API to search for playlists
        results = sp.search(q=search_query, limit=10, type='playlist')

        # Extract playlist details
        playlists = []
        for playlist in results.get('playlists', {}).get('items', []):
            if playlist:
                playlists.append({
                    'name': playlist.get('name', 'Unknown Playlist'),
                    'description': playlist.get('description', 'No description available'),
                    'url': playlist.get('external_urls', {}).get('spotify', '#')
                })

        if not playlists:
            print("No playlists found. Returning a default playlist.")
            playlists = [{'name': 'Default Playlist', 'description': 'A fallback playlist', 'url': '#'}]

        return playlists

    except Exception as e:
        print(f"Error fetching Spotify recommendations: {e}")
        return [{'name': 'Error Playlist', 'description': 'Unable to fetch data', 'url': '#'}]
def get_youtube_recommendations(user_id, mood):
    preferences = get_user_preferences(user_id)  # Fetch user preferences

    # Define mood-specific YouTube keywords
    mood_keywords = {
        'Happy': ['happy music playlist', 'feel good songs', 'upbeat dance', 'party playlist', 'positive vibes'],
        'Sad': ['melancholic music', 'sad music playlist', 'slow songs', 'sad piano', 'heartbreak songs'],
        'Angry': ['angry music playlist', 'hard rock music', 'intense songs', 'metal music', 'rage music'],
        'Surprise': ['surprise reactions', 'unexpected moments', 'shock reactions', 'funny surprises', 'intense dubstep'],
        'Neutral': ['chill music playlist', 'relaxing instrumental', 'lo-fi beats', 'calming music for stress']
    }

    search_query = mood_keywords.get(mood, ['chill music playlist'])[0]  # Default to the first keyword

    # Add user preferences to the query
    if preferences:
        preferred_artists = [pref.get('artist', '') for pref in preferences if 'artist' in pref]
        search_query += " " + " ".join(preferred_artists)

    try:
        # Call YouTube API
        request = youtube.search().list(part="snippet", q=search_query, type="video", maxResults=5)
        response = request.execute()

        # Extract video details
        videos = []
        for item in response.get('items', []):
            videos.append({
                'title': item['snippet'].get('title', 'Unknown Video'),
                'url': f"https://www.youtube.com/watch?v={item['id']['videoId']}"
            })

        if not videos:
            print("No YouTube videos found. Returning a default video.")
            videos = [{'title': 'Default Video', 'url': 'https://www.youtube.com'}]

        return videos

    except Exception as e:
        print(f"Error fetching YouTube recommendations: {e}")
        return [{'title': 'Error Video', 'url': 'https://www.youtube.com'}]

def get_instagram_recommendations(user_id, mood):
    preferences = get_instagram_hashtags(user_id)  # Fetch user preferences

    # Define mood-specific Instagram hashtags
    mood_keywords = {
        'Happy': ['#HappyVibes', '#GoodVibesOnly', '#FeelGood', '#PositiveVibes', '#PartyTime'],
        'Sad': ['#SadVibes', '#Melancholy', '#TearJerker', '#Heartbreak', '#LostInSadness'],
        'Angry': ['#Rage', '#Anger', '#Intensity', '#Fury', '#NoControl'],
        'Surprise': ['#SurpriseReaction', '#Unexpected', '#ShockingMoments', '#SurpriseVideo'],
        'Neutral': ['#ChillVibes', '#Relax', '#Calm', '#PeacefulVibes', '#MoodReset']
    }

    hashtags = mood_keywords.get(mood, ['#Relax'])  # Default hashtag

    # Add user-preferred hashtags
    if preferences:
        hashtags += [pref for pref in preferences if pref.startswith('#')]

    try:
        # Simulate Instagram scraping/Graph API response
        posts = []
        for hashtag in hashtags:
            posts.append({
                'image': f'https://www.instagram.com/explore/tags/{hashtag.strip("#")}/',
                'caption': f'Explore {hashtag} posts',
                'url': f'https://www.instagram.com/explore/tags/{hashtag.strip("#")}/'
            })

        if not posts:
            print("No Instagram posts found. Returning a default post.")
            posts = [{'image': '#', 'caption': 'Default Post', 'url': 'https://www.instagram.com'}]

        return posts

    except Exception as e:
        print(f"Error fetching Instagram recommendations: {e}")
        return [{'image': '#', 'caption': 'Error Post', 'url': 'https://www.instagram.com'}]


@app.route('/home', methods=['GET', 'POST'])
@login_required
def home():
    if request.method == 'POST':
        if 'file' in request.files:
            file = request.files['file']
            file.save('uploaded_frame.jpg')  # Save frame temporarily

            # Detect mood from the uploaded image
            # mood = detect_emotion('uploaded_frame.jpg')
            mood = "Sad"  # You can integrate the emotion detection logic here
            save_user_mood(current_user.id, mood)  # Store detected mood

            # Fetch recommendations based on mood and user data
            spotify_recommendations = get_spotify_recommendations(current_user.id, mood)
            youtube_recommendations = get_youtube_recommendations(current_user.id, mood)
            instagram_recommendations = get_instagram_recommendations(current_user.id, mood)

            return jsonify({
                'mood': mood,
                'spotify': spotify_recommendations,
                'youtube': youtube_recommendations,
                'instagram': instagram_recommendations
            })

    return render_template('home.html')

if __name__ == "__main__":
    app.run(debug=True)
