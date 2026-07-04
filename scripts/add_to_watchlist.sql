INSERT INTO watchlist_schedule (anime_name, expected_weekday, last_seen_date)
VALUES ('Kill Blue', 5, '7/4')
ON CONFLICT(anime_name) DO UPDATE SET
    expected_weekday = excluded.expected_weekday,
    last_seen_date = excluded.last_seen_date;