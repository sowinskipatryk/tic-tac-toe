CREATE TABLE game_stats (
    id SERIAL PRIMARY KEY,
    player_id VARCHAR(36),
    wins INTEGER,
    draws INTEGER,
    losses INTEGER,
    games_length INTERVAL DEFAULT '00:00:00',
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
