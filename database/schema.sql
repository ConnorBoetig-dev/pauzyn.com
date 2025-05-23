-- Enable required extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "vector";

-- Create users table
CREATE TABLE IF NOT EXISTS users (
    id SERIAL PRIMARY KEY,
    email VARCHAR(120) UNIQUE NOT NULL,
    username VARCHAR(80) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    full_name VARCHAR(120),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    is_active BOOLEAN DEFAULT TRUE
);

-- Create index on email for faster lookups
CREATE INDEX IF NOT EXISTS idx_users_email ON users(email);

-- Create videos table
CREATE TABLE IF NOT EXISTS videos (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    
    -- Basic information
    title VARCHAR(255) NOT NULL,
    description TEXT,
    filename VARCHAR(255) NOT NULL,
    s3_key VARCHAR(500) UNIQUE NOT NULL,
    s3_url VARCHAR(1000),
    thumbnail_url VARCHAR(1000),
    
    -- Video metadata
    duration FLOAT,
    file_size BIGINT,
    format VARCHAR(50),
    resolution VARCHAR(20),
    fps FLOAT,
    
    -- Processing status
    status VARCHAR(50) DEFAULT 'pending',
    processing_started_at TIMESTAMP,
    processing_completed_at TIMESTAMP,
    error_message TEXT,
    
    -- AI Analysis Results (JSONB for flexibility)
    detected_objects JSONB,
    detected_scenes JSONB,
    detected_faces JSONB,
    detected_emotions JSONB,
    moderation_labels JSONB,
    
    -- Transcription and text analysis
    transcript TEXT,
    detected_languages JSONB,
    key_phrases JSONB,
    sentiment_analysis JSONB,
    entities JSONB,
    
    -- Search and categorization
    tags TEXT[],
    categories TEXT[],
    
    -- Vector embeddings
    visual_embedding vector(1536),
    audio_embedding vector(1536),
    combined_embedding vector(1536),
    
    -- Timestamps
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Create indexes for better performance
CREATE INDEX IF NOT EXISTS idx_videos_user_id ON videos(user_id);
CREATE INDEX IF NOT EXISTS idx_videos_status ON videos(status);
CREATE INDEX IF NOT EXISTS idx_videos_created_at ON videos(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_videos_tags ON videos USING GIN(tags);
CREATE INDEX IF NOT EXISTS idx_videos_categories ON videos USING GIN(categories);

-- Create indexes for vector similarity search
CREATE INDEX IF NOT EXISTS idx_videos_visual_embedding ON videos 
    USING ivfflat (visual_embedding vector_cosine_ops) 
    WITH (lists = 100);

CREATE INDEX IF NOT EXISTS idx_videos_audio_embedding ON videos 
    USING ivfflat (audio_embedding vector_cosine_ops) 
    WITH (lists = 100);

CREATE INDEX IF NOT EXISTS idx_videos_combined_embedding ON videos 
    USING ivfflat (combined_embedding vector_cosine_ops) 
    WITH (lists = 100);

-- Create function to update timestamp
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ language 'plpgsql';

-- Create triggers for updated_at
CREATE TRIGGER update_users_updated_at BEFORE UPDATE
    ON users FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_videos_updated_at BEFORE UPDATE
    ON videos FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- Create view for video search results
CREATE OR REPLACE VIEW video_search_view AS
SELECT 
    v.id,
    v.title,
    v.description,
    v.thumbnail_url,
    v.duration,
    v.tags,
    v.categories,
    v.created_at,
    u.username as owner_username,
    u.id as owner_id
FROM videos v
JOIN users u ON v.user_id = u.id
WHERE v.status = 'completed';

-- Sample data for testing (optional)
-- INSERT INTO users (email, username, password_hash, full_name) 
-- VALUES ('test@example.com', 'testuser', 'hashed_password_here', 'Test User');

-- Grant permissions (adjust based on your database user)
-- GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO your_db_user;
-- GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO your_db_user;
-- GRANT ALL PRIVILEGES ON ALL FUNCTIONS IN SCHEMA public TO your_db_user;