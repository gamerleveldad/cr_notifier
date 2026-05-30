INSERT INTO watch_history (anime_name, status, user_rating)
VALUES ('Boring Filler Show', 'Dropped', 'Disliked')
ON CONFLICT(anime_name) DO UPDATE SET
    status = excluded.status,
    user_rating = excluded.user_rating;