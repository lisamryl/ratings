"""Movie Ratings."""

from jinja2 import StrictUndefined

from flask import (Flask, render_template, redirect, request, flash,
                   session, jsonify)
from flask_debugtoolbar import DebugToolbarExtension
from flask_sqlalchemy import SQLAlchemy
from model import User, Rating, Movie, Genre, Job, connect_to_db, db


app = Flask(__name__)
# app.config['JSON_SORT_KEYS'] = False

# Required to use Flask sessions and the debug toolbar
app.secret_key = "ABC"

# Normally, if you use an undefined variable in Jinja2, it fails
# silently. This is horrible. Fix this so that, instead, it raises an
# error.
app.jinja_env.undefined = StrictUndefined


def ave_rating(movie):
    rating_scores = [r.score for r in movie.ratings]
    avg_rating = round(float(sum(rating_scores)) / len(rating_scores), 1)
    return avg_rating


def get_user_rating(user_id, movie_id):
    user_rating = Rating.query.filter_by(movie_id=movie_id, user_id=user_id).first()
    return user_rating


def get_prediction(user_id, movie, user_rating):
    #have they ever rated anything?
    user_all_rating = Rating.query.filter_by(user_id=user_id).count()

    # Prediction code: only predict if the user hasn't rated it.
    prediction = None

    #This will only show a prediction if the user hasn't rated this movie.
    #Also, will not try to guess a rating if user has never rated 0 or 1 movies.
    if (not user_rating) and (user_all_rating > 1):
        user = User.query.get(user_id)
        if user:
            prediction = round(float(user.predict_rating(movie)), 1)
        else:
            return None
    else:
        return None
    return prediction

@app.route('/')
def index():
    """Homepage."""

    return render_template("homepage.html")


@app.route('/users')
def user_list():
    """Show list of users."""

    users = User.query.all()
    return render_template("user_list.html", users=users)


@app.route('/register')
def register_form():
    """Prompts user to register/sign in"""

    return render_template("register_form.html")


@app.route('/register', methods=['POST'])
def register_process():
    """Adds new user to DB"""
    # gets information from input form
    email = request.form.get('email')
    password = request.form.get('password')
    # fetch that user from DB as object
    db_user = User.query.filter(User.email == email).first()

    # if that user exists in DB:
    if db_user:
        # verify password, redirect to their user info page;
        # add user_id to the session
        if db_user.password == password:
            session['user_id'] = db_user.user_id
            flash("You have successfully logged in!")
            url = '/users/{}'.format(db_user.user_id)
            return redirect(url)
        else:
            # if password doesn't match, redirect to register page
            flash("Wrong credentials, try again")
            return redirect('/register')
    else:
        # register new user; add to DB; log them in; save user_id to session
        new_user = User(email=email, password=password)
        db.session.add(new_user)
        db.session.commit()
        flash("You're now added as a new user! Welcome!")
        session['user_id'] = new_user.user_id
        url = '/users/{}'.format(new_user.user_id)
        # redirect to the user's info page
        return redirect(url)


@app.route('/logout')
def log_out():
    """Logs a user out"""
    del session['user_id']
    flash("You have successfully logged out!")

    return redirect("/")


@app.route('/users/<user_id>')
def show_user_details(user_id):
    """Shows specific user's details"""
    user = User.query.filter(User.user_id == user_id).one()
    return render_template("user_details.html", user=user)


@app.route('/movies')
def show_movies():
    """Shows list of all movies"""
    movies = Movie.query.all()
    genres = Genre.query.filter(Genre.name != 'unknown').all()
    return render_template("movies.html", movies=movies, genres=genres)


@app.route('/movies/<movie_id>')
def movie_detail(movie_id):
    """Show info about movie.

    If a user is logged in, let them add/edit a rating.
    """
    user_id = session.get("user_id")
    movie = Movie.query.get(movie_id)
    avg_rating = ave_rating(movie)

    if user_id:
        user_rating = get_user_rating(user_id, movie_id)
        prediction = get_prediction(user_id, movie, user_rating)
    else:
        prediction = None
        user_rating = None

    return render_template(
        "movie_details.html",
        movie=movie,
        user_rating=user_rating,
        average=avg_rating,
        prediction=prediction
        )


@app.route('/rating_handler', methods=['POST'])
def handle_rating():
    """Handles user input form for rating"""
    #get fields from the form and session
    new_rating = request.form.get("rating")
    movie_id = request.form.get("movie_id")
    user_id = session['user_id']

    #pull rating row for user and movie id, if it exists
    rating = Rating.query.filter(Rating.movie_id == movie_id,
                                 Rating.user_id == user_id).first()

    #if the row is there, this movie was already rated - need to update in DB.
    if rating:
        rating.score = new_rating
        db.session.commit()
        #inform user rating was updated
        flash("Your rating has been updated!")
    else:
        #if row was not there, create new instance and add to DB.
        rating = Rating(movie_id=movie_id,
                        user_id=user_id,
                        score=new_rating)
        db.session.add(rating)
        db.session.commit()
        #inform user rating was added
        flash("Your rating has been added")
    url = "/movies/{}".format(movie_id)
    #redirect back to movie page, which now shows user's new/updated rating.
    return redirect(url)


@app.route('/movie-filter.json')
def filter_movies():
    """Returns filtered movie list."""

    input_genre = request.args.get("inputGenre")

    if input_genre == "all":
        movie_list = Movie.query.all()
    else:
        genre = Genre.query.filter(Genre.name == input_genre).first()
        movie_list = genre.movies

    movies = {}

    for movie in movie_list:
        movies[movie.title] = movie.movie_id

    return jsonify(movies)


if __name__ == "__main__":
    # We have to set debug=True here, since it has to be True at the
    # point that we invoke the DebugToolbarExtension
    app.debug = True
    app.jinja_env.auto_reload = app.debug  # make sure templates, etc. are not cached in debug mode

    connect_to_db(app)

    # Use the DebugToolbar
    DebugToolbarExtension(app)

    app.run(port=5000, host='0.0.0.0')
