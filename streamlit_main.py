import requests
import streamlit as st
import base64


# ============================================================
# CONFIG
# ============================================================

API_BASE = "https://hybrid-movie-recommendation-system-dq65.onrender.com"
TMDB_IMG = "https://image.tmdb.org/t/p/w500"

st.set_page_config(
    page_title="MovieVerse AI",
    page_icon="🎬",
    layout="wide",
    initial_sidebar_state="expanded",
)


# ============================================================
# LOAD CUSTOM CSS
# ============================================================

def load_css():

    css_path = "static/css/style.css"
    bg_path = "static/images/bg.jpeg"

    try:

        with open(css_path, "r", encoding="utf-8") as file:
            css = file.read()

        # ----------------------------------------------------
        # Load background image as Base64
        # ----------------------------------------------------

        try:

            with open(bg_path, "rb") as file:
                bg_data = base64.b64encode(
                    file.read()
                ).decode("utf-8")

            css = css.replace(
                "../images/bg.jpeg",
                f"data:image/jpeg;base64,{bg_data}"
            )

        except Exception:
            pass

        st.markdown(
            f"<style>{css}</style>",
            unsafe_allow_html=True
        )

    except Exception as error:

        st.warning(
            f"Could not load custom styling: {error}"
        )


load_css()


# ============================================================
# SESSION STATE
# ============================================================

if "view" not in st.session_state:
    st.session_state.view = "home"

if "selected_tmdb_id" not in st.session_state:
    st.session_state.selected_tmdb_id = None


# ============================================================
# URL ROUTING
# ============================================================

try:

    query_view = st.query_params.get("view")
    query_id = st.query_params.get("id")

    if query_view in ("home", "details"):
        st.session_state.view = query_view

    if query_id:

        try:

            st.session_state.selected_tmdb_id = int(
                query_id
            )

            st.session_state.view = "details"

        except Exception:
            pass

except Exception:
    pass


# ============================================================
# NAVIGATION
# ============================================================

def goto_home():

    st.session_state.view = "home"
    st.session_state.selected_tmdb_id = None

    try:

        st.query_params["view"] = "home"

        if "id" in st.query_params:
            del st.query_params["id"]

    except Exception:
        pass

    st.rerun()


def goto_details(tmdb_id):

    if not tmdb_id:
        return

    st.session_state.view = "details"
    st.session_state.selected_tmdb_id = int(tmdb_id)

    try:

        st.query_params["view"] = "details"
        st.query_params["id"] = str(int(tmdb_id))

    except Exception:
        pass

    st.rerun()


# ============================================================
# API HELPER
# ============================================================

@st.cache_data(ttl=30)
def api_get_json(path, params=None):

    try:

        response = requests.get(
            f"{API_BASE}{path}",
            params=params,
            timeout=25
        )

        if response.status_code >= 400:

            return None, (
                f"HTTP {response.status_code}: "
                f"{response.text[:300]}"
            )

        return response.json(), None

    except requests.exceptions.ConnectionError:

        return None, (
            "Cannot connect to the MovieVerse API. "
            "Make sure your FastAPI backend is running "
            "on port 8000."
        )

    except requests.exceptions.Timeout:

        return None, (
            "The MovieVerse API took too long to respond."
        )

    except Exception as error:

        return None, f"Request failed: {error}"


# ============================================================
# NORMALIZE MOVIE
# ============================================================

def normalize_movie(movie):

    if not isinstance(movie, dict):
        return None

    tmdb_id = (
        movie.get("tmdb_id")
        or movie.get("id")
    )

    title = (
        movie.get("title")
        or movie.get("name")
        or "Untitled"
    )

    if not tmdb_id:
        return None

    poster_url = movie.get("poster_url")

    # --------------------------------------------------------
    # Build poster URL from poster_path if necessary
    # --------------------------------------------------------

    if not poster_url:

        poster_path = movie.get("poster_path")

        if poster_path:

            poster_url = (
                f"{TMDB_IMG}{poster_path}"
            )

    return {
        "tmdb_id": int(tmdb_id),
        "title": str(title),
        "poster_url": poster_url,
        "release_date": (
            movie.get("release_date")
            or ""
        ),
        "vote_average": (
            movie.get("vote_average")
            or movie.get("rating")
        ),
    }


# ============================================================
# TF-IDF → MOVIE CARDS
# ============================================================

def to_cards_from_tfidf_items(items):

    cards = []

    for item in items or []:

        if not isinstance(item, dict):
            continue

        tmdb = item.get("tmdb") or {}

        if not tmdb:
            continue

        movie = normalize_movie(
            {
                **tmdb,
                "title": (
                    tmdb.get("title")
                    or item.get("title")
                )
            }
        )

        if movie:
            cards.append(movie)

    return cards


# ============================================================
# SEARCH PARSER
# ============================================================

def parse_tmdb_search_to_cards(
    data,
    keyword,
    limit=24
):

    keyword_lower = (
        keyword.strip().lower()
    )

    raw_items = []

    # ========================================================
    # FORMAT 1
    # {"results": [...]}
    # ========================================================

    if isinstance(data, dict) and "results" in data:

        for movie in data.get("results") or []:

            normalized = normalize_movie(movie)

            if normalized:
                raw_items.append(normalized)

    # ========================================================
    # FORMAT 2
    # [...]
    # ========================================================

    elif isinstance(data, list):

        for movie in data:

            normalized = normalize_movie(movie)

            if normalized:
                raw_items.append(normalized)

    else:

        return [], []

    # ========================================================
    # MATCH SEARCH KEYWORD
    # ========================================================

    matched = [
        movie
        for movie in raw_items
        if keyword_lower
        in movie["title"].lower()
    ]

    final_list = (
        matched
        if matched
        else raw_items
    )

    # ========================================================
    # SUGGESTIONS
    # ========================================================

    suggestions = []

    for movie in final_list[:10]:

        release_date = (
            movie.get("release_date")
            or ""
        )

        year = release_date[:4]

        if year:

            label = (
                f"{movie['title']} "
                f"({year})"
            )

        else:

            label = movie["title"]

        suggestions.append(
            (
                label,
                movie["tmdb_id"]
            )
        )

    # ========================================================
    # CARDS
    # ========================================================

    cards = final_list[:limit]

    return suggestions, cards


# ============================================================
# MOVIE GRID
# ============================================================

def poster_grid(
    cards,
    cols=6,
    key_prefix="grid"
):

    if not cards:

        st.info(
            "No movies to show right now."
        )

        return

    # Safety
    cols = max(1, min(int(cols), 8))

    rows = (
        len(cards) + cols - 1
    ) // cols

    index = 0

    for row in range(rows):

        columns = st.columns(
            cols,
            gap="medium"
        )

        for column_index in range(cols):

            if index >= len(cards):
                break

            movie = cards[index]

            current_index = index

            index += 1

            tmdb_id = movie.get(
                "tmdb_id"
            )

            title = movie.get(
                "title",
                "Untitled"
            )

            poster = movie.get(
                "poster_url"
            )

            release_date = (
                movie.get("release_date")
                or ""
            )

            year = release_date[:4]

            rating = (
                movie.get("vote_average")
                or movie.get("rating")
            )

            # ------------------------------------------------
            # CARD
            # ------------------------------------------------

            with columns[column_index]:

                # Poster
                if poster:

                    st.image(
                        poster,
                        use_container_width=True
                    )

                else:

                    st.markdown(
                        "🎬",
                        help="No poster available"
                    )

                # Title
                st.markdown(
                    f"**{title}**"
                )

                # Rating / year
                meta = []

                if rating is not None:

                    try:

                        rating_value = float(
                            rating
                        )

                        if rating_value > 0:

                            meta.append(
                                f"⭐ {rating_value:.1f}"
                            )

                    except Exception:
                        pass

                if year:
                    meta.append(
                        f"📅 {year}"
                    )

                if meta:

                    st.caption(
                        "  •  ".join(meta)
                    )

                # Details button
                if tmdb_id:

                    if st.button(
                        "🎬 View Details",
                        key=(
                            f"{key_prefix}_"
                            f"{row}_"
                            f"{column_index}_"
                            f"{current_index}_"
                            f"{tmdb_id}"
                        ),
                        use_container_width=True
                    ):

                        goto_details(
                            tmdb_id
                        )


# ============================================================
# SIDEBAR
# ============================================================

with st.sidebar:

    st.markdown(
        "🍿 # MovieVerse"
    )

    st.caption(
        "AI Movie Recommendation"
    )

    st.divider()

    st.subheader(
        "🎬 Menu"
    )

    if st.button(
        "🏠 Home",
        use_container_width=True,
        key="sidebar_home"
    ):

        goto_home()

    st.divider()

    st.subheader(
        "🏠 Home Feed"
    )

    home_category = st.selectbox(
        "Category",
        [
            "trending",
            "popular",
            "top_rated",
            "now_playing",
            "upcoming"
        ],
        index=0,
        key="home_category"
    )

    grid_cols = st.slider(
        "Grid columns",
        min_value=4,
        max_value=8,
        value=6,
        key="grid_columns"
    )

    st.divider()

    st.caption(
        "Powered by TMDB • TF-IDF • "
        "Machine Learning"
    )


# ============================================================
# MAIN HEADER
# ============================================================

st.title(
    "🎬 MovieVerse AI"
)

st.subheader(
    "Discover Movies with Artificial Intelligence"
)

st.write(
    "Explore thousands of movies using "
    "intelligent search and recommendation."
)

st.caption(
    "Powered by TF-IDF • TMDB API • Machine Learning"
)

st.divider()


# ============================================================
# HOME PAGE
# ============================================================

if st.session_state.view == "home":

    # --------------------------------------------------------
    # Search heading
    # --------------------------------------------------------

    st.header(
        "🔎 Find Your Next Movie"
    )

    st.write(
        "Search thousands of movies using "
        "TMDB intelligent search."
    )

    # --------------------------------------------------------
    # Search box
    # --------------------------------------------------------

    typed = st.text_input(
        "Search by movie title",
        placeholder=(
            "Try: Avengers, Batman, "
            "Inception, Love..."
        ),
        key="movie_search"
    )

    # ========================================================
    # SEARCH MODE
    # ========================================================

    if typed.strip():

        search_text = typed.strip()

        if len(search_text) < 2:

            st.info(
                "Type at least 2 characters "
                "for movie suggestions."
            )

        else:

            data, error = api_get_json(
                "/tmdb/search",
                params={
                    "query": search_text
                }
            )

            if error or data is None:

                st.error(
                    f"Search failed: {error}"
                )

            else:

                suggestions, cards = (
                    parse_tmdb_search_to_cards(
                        data,
                        search_text,
                        limit=24
                    )
                )

                # ------------------------------------------------
                # Suggestions
                # ------------------------------------------------

                if suggestions:

                    labels = [
                        "-- Select a movie --"
                    ]

                    labels.extend(
                        [
                            item[0]
                            for item in suggestions
                        ]
                    )

                    selected = st.selectbox(
                        "🎯 Movie Suggestions",
                        labels,
                        index=0,
                        key="movie_suggestions"
                    )

                    if (
                        selected
                        != "-- Select a movie --"
                    ):

                        selected_id = None

                        for label, movie_id in suggestions:

                            if label == selected:

                                selected_id = movie_id
                                break

                        if selected_id:

                            goto_details(
                                selected_id
                            )

                else:

                    st.info(
                        "No suggestions found. "
                        "Try another keyword."
                    )

                # ------------------------------------------------
                # Search results
                # ------------------------------------------------

                st.header(
                    "🎬 Search Results"
                )

                poster_grid(
                    cards,
                    cols=grid_cols,
                    key_prefix="search_results"
                )

        st.stop()

    # ========================================================
    # HOME FEED
    # ========================================================

    category_name = (
        home_category
        .replace("_", " ")
        .title()
    )

    st.header(
        f"🔥 {category_name}"
    )

    home_cards, error = api_get_json(
        "/home",
        params={
            "category": home_category,
            "limit": 24
        }
    )

    if error:

        st.error(
            f"Home feed failed: {error}"
        )

        st.stop()

    if not home_cards:

        st.warning(
            "No movies were returned "
            "by the API."
        )

        st.stop()

    poster_grid(
        home_cards,
        cols=grid_cols,
        key_prefix="home_feed"
    )


# ============================================================
# DETAILS PAGE
# ============================================================

elif st.session_state.view == "details":

    tmdb_id = (
        st.session_state.selected_tmdb_id
    )

    # --------------------------------------------------------
    # No selected movie
    # --------------------------------------------------------

    if not tmdb_id:

        st.warning(
            "No movie selected."
        )

        if st.button(
            "← Back to Home"
        ):

            goto_home()

        st.stop()

    # --------------------------------------------------------
    # Top navigation
    # --------------------------------------------------------

    left_top, right_top = st.columns(
        [4, 1]
    )

    with left_top:

        st.header(
            "📄 Movie Details"
        )

    with right_top:

        if st.button(
            "← Back",
            use_container_width=True,
            key="details_back"
        ):

            goto_home()

    # --------------------------------------------------------
    # Movie details API
    # --------------------------------------------------------

    data, error = api_get_json(
        f"/movie/id/{tmdb_id}"
    )

    if error or not data:

        st.error(
            "Could not load movie details: "
            f"{error or 'Unknown error'}"
        )

        st.stop()

    # --------------------------------------------------------
    # Basic movie data
    # --------------------------------------------------------

    title = (
        data.get("title")
        or "Unknown Movie"
    )

    release = (
        data.get("release_date")
        or "-"
    )

    overview = (
        data.get("overview")
        or "No overview available."
    )

    poster_url = data.get(
        "poster_url"
    )

    backdrop_url = data.get(
        "backdrop_url"
    )

    rating = (
        data.get("vote_average")
        or data.get("rating")
    )

    genres_data = (
        data.get("genres")
        or []
    )

    # --------------------------------------------------------
    # Genre names
    # --------------------------------------------------------

    genre_names = []

    for genre in genres_data:

        if isinstance(genre, dict):

            name = genre.get(
                "name"
            )

        else:

            name = str(genre)

        if name:
            genre_names.append(
                name
            )

    # ========================================================
    # MOVIE INFORMATION
    # ========================================================

    poster_column, info_column = st.columns(
        [1, 2.4],
        gap="large"
    )

    # --------------------------------------------------------
    # Poster
    # --------------------------------------------------------

    with poster_column:

        if poster_url:

            st.image(
                poster_url,
                use_container_width=True
            )

        else:

            st.info(
                "🖼️ No poster available"
            )

    # --------------------------------------------------------
    # Information
    # --------------------------------------------------------

    with info_column:

        st.title(
            title
        )

        st.write(
            f"📅 **Release Date:** {release}"
        )

        if rating is not None:

            try:

                rating_value = float(
                    rating
                )

                if rating_value > 0:

                    st.write(
                        f"⭐ **Rating:** "
                        f"{rating_value:.1f} / 10"
                    )

            except Exception:
                pass

        if genre_names:

            st.write(
                "🎭 **Genres:** "
                + ", ".join(genre_names)
            )

        st.divider()

        st.subheader(
            "📖 Overview"
        )

        st.write(
            overview
        )

    # ========================================================
    # BACKDROP
    # ========================================================

    if backdrop_url:

        st.divider()

        st.subheader(
            "🎞️ Movie Backdrop"
        )

        st.image(
            backdrop_url,
            use_container_width=True
        )

    # ========================================================
    # RECOMMENDATIONS
    # ========================================================

    st.divider()

    st.header(
        "🤖 AI Recommendations"
    )

    movie_title = (
        data.get("title")
        or ""
    ).strip()

    if not movie_title:

        st.warning(
            "No movie title available "
            "to calculate recommendations."
        )

        st.stop()

    # --------------------------------------------------------
    # TF-IDF + genre recommendations
    # --------------------------------------------------------

    bundle, recommendation_error = api_get_json(
        "/movie/search",
        params={
            "query": movie_title,
            "tfidf_top_n": 12,
            "genre_limit": 12
        }
    )

    if (
        not recommendation_error
        and bundle
    ):

        # ====================================================
        # TF-IDF
        # ====================================================

        st.subheader(
            "🔎 Similar Movies — TF-IDF"
        )

        tfidf_items = (
            bundle.get(
                "tfidf_recommendations"
            )
            or []
        )

        tfidf_cards = (
            to_cards_from_tfidf_items(
                tfidf_items
            )
        )

        poster_grid(
            tfidf_cards,
            cols=grid_cols,
            key_prefix="details_tfidf"
        )

        # ====================================================
        # GENRE
        # ====================================================

        st.subheader(
            "🎭 More Like This — Genre"
        )

        genre_cards = (
            bundle.get(
                "genre_recommendations"
            )
            or []
        )

        poster_grid(
            genre_cards,
            cols=grid_cols,
            key_prefix="details_genre"
        )

    else:

        # ====================================================
        # FALLBACK
        # ====================================================

        st.info(
            "TF-IDF recommendations are "
            "currently unavailable. "
            "Showing genre recommendations instead."
        )

        genre_only, error3 = api_get_json(
            "/recommend/genre",
            params={
                "tmdb_id": tmdb_id,
                "limit": 18
            }
        )

        if not error3 and genre_only:

            poster_grid(
                genre_only,
                cols=grid_cols,
                key_prefix="details_genre_fallback"
            )

        else:

            st.warning(
                "No recommendations are "
                "available right now."
            )


# ============================================================
# FOOTER
# ============================================================

st.divider()

st.caption(
    "🎬 MovieVerse AI • "
    "Intelligent Movie Recommendation System • "
    "TMDB • TF-IDF • Machine Learning"
)
