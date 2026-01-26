-- Create auth schema and required extensions
CREATE SCHEMA IF NOT EXISTS auth;
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS pgcrypto;

-- Create roles
DO $$
BEGIN
  IF NOT EXISTS (SELECT FROM pg_catalog.pg_roles WHERE rolname = 'anon') THEN
    CREATE ROLE anon NOLOGIN NOINHERIT;
  END IF;
  IF NOT EXISTS (SELECT FROM pg_catalog.pg_roles WHERE rolname = 'authenticated') THEN
    CREATE ROLE authenticated NOLOGIN NOINHERIT;
  END IF;
  IF NOT EXISTS (SELECT FROM pg_catalog.pg_roles WHERE rolname = 'service_role') THEN
    CREATE ROLE service_role NOLOGIN NOINHERIT BYPASSRLS;
  END IF;
END
$$;

-- Grant necessary permissions
GRANT USAGE ON SCHEMA public TO anon, authenticated, service_role;
GRANT ALL ON SCHEMA public TO service_role;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON TABLES TO service_role;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON SEQUENCES TO service_role;

GRANT USAGE ON SCHEMA auth TO anon, authenticated, service_role;
GRANT ALL ON SCHEMA auth TO service_role;

-- Example: Create a user_profiles table linked to auth
CREATE TABLE IF NOT EXISTS public.user_profiles (
  id UUID PRIMARY KEY REFERENCES auth.users(id) ON DELETE CASCADE,
  username TEXT UNIQUE,
  full_name TEXT,
  avatar_url TEXT,
  created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
  updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Enable Row Level Security
ALTER TABLE public.user_profiles ENABLE ROW LEVEL SECURITY;

-- Create policies for user_profiles
CREATE POLICY "Users can view their own profile"
  ON public.user_profiles FOR SELECT
  USING (auth.uid() = id);

CREATE POLICY "Users can update their own profile"
  ON public.user_profiles FOR UPDATE
  USING (auth.uid() = id);

CREATE POLICY "Users can insert their own profile"
  ON public.user_profiles FOR INSERT
  WITH CHECK (auth.uid() = id);

-- Grant permissions on user_profiles table
GRANT SELECT, INSERT, UPDATE ON public.user_profiles TO authenticated;
GRANT SELECT ON public.user_profiles TO anon;
GRANT ALL ON public.user_profiles TO service_role;

-- Example: Create a simple tarxiv_user_data table for user-specific astronomical data
CREATE TABLE IF NOT EXISTS public.tarxiv_user_data (
  id UUID DEFAULT uuid_generate_v4() PRIMARY KEY,
  user_id UUID REFERENCES auth.users(id) ON DELETE CASCADE NOT NULL,
  object_name TEXT NOT NULL,
  notes TEXT,
  tags TEXT[],
  is_favorite BOOLEAN DEFAULT FALSE,
  created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
  updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
  UNIQUE(user_id, object_name)
);

ALTER TABLE public.tarxiv_user_data ENABLE ROW LEVEL SECURITY;

-- Policies for tarxiv_user_data
CREATE POLICY "Users can view their own data"
  ON public.tarxiv_user_data FOR SELECT
  USING (auth.uid() = user_id);

CREATE POLICY "Users can insert their own data"
  ON public.tarxiv_user_data FOR INSERT
  WITH CHECK (auth.uid() = user_id);

CREATE POLICY "Users can update their own data"
  ON public.tarxiv_user_data FOR UPDATE
  USING (auth.uid() = user_id);

CREATE POLICY "Users can delete their own data"
  ON public.tarxiv_user_data FOR DELETE
  USING (auth.uid() = user_id);

GRANT ALL ON public.tarxiv_user_data TO authenticated;
GRANT SELECT ON public.tarxiv_user_data TO anon;
GRANT ALL ON public.tarxiv_user_data TO service_role;

-- Institutions catalog
CREATE TABLE IF NOT EXISTS public.institutions (
  id UUID DEFAULT uuid_generate_v4() PRIMARY KEY,
  name TEXT UNIQUE NOT NULL,
  website TEXT,
  description TEXT,
  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW()
);

ALTER TABLE public.institutions ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Institutions readable by anyone"
  ON public.institutions FOR SELECT
  USING (TRUE);

CREATE POLICY "Institutions managed by service role only"
  ON public.institutions FOR ALL
  USING (FALSE)
  WITH CHECK (FALSE);

GRANT SELECT ON public.institutions TO anon, authenticated;
GRANT ALL ON public.institutions TO service_role;

-- Core user profile + relationships
CREATE TABLE IF NOT EXISTS public.users (
  id UUID PRIMARY KEY REFERENCES auth.users(id) ON DELETE CASCADE,
  provider_user_id TEXT,
  username TEXT UNIQUE,
  nickname TEXT,
  email TEXT,
  institution_id UUID REFERENCES public.institutions(id) ON DELETE SET NULL,
  institution TEXT,
  forename TEXT,
  surname TEXT,
  picture_url TEXT,
  bio TEXT,
  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW()
);

ALTER TABLE public.users ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Users can view their own user row"
  ON public.users FOR SELECT
  USING (auth.uid() = id);

CREATE POLICY "Users can insert their own user row"
  ON public.users FOR INSERT
  WITH CHECK (auth.uid() = id);

CREATE POLICY "Users can update their own user row"
  ON public.users FOR UPDATE
  USING (auth.uid() = id);

GRANT SELECT, INSERT, UPDATE ON public.users TO authenticated;
GRANT SELECT ON public.users TO anon;
GRANT ALL ON public.users TO service_role;

CREATE TABLE IF NOT EXISTS public.tags (
  id UUID DEFAULT uuid_generate_v4() PRIMARY KEY,
  name TEXT UNIQUE NOT NULL,
  description TEXT,
  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW()
);

ALTER TABLE public.tags ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Tags readable by anyone"
  ON public.tags FOR SELECT
  USING (TRUE);

CREATE POLICY "Tags managed by service role only"
  ON public.tags FOR ALL
  USING (FALSE)
  WITH CHECK (FALSE);

GRANT SELECT ON public.tags TO anon, authenticated;
GRANT ALL ON public.tags TO service_role;

CREATE TABLE IF NOT EXISTS public.teams (
  id UUID DEFAULT uuid_generate_v4() PRIMARY KEY,
  name TEXT UNIQUE NOT NULL,
  description TEXT,
  admin_user_id UUID REFERENCES public.users(id) ON DELETE SET NULL,
  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW()
);

ALTER TABLE public.teams ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Teams are readable to authenticated users"
  ON public.teams FOR SELECT
  USING (TRUE);

CREATE POLICY "Team insert ties admin to current user"
  ON public.teams FOR INSERT
  WITH CHECK (auth.uid() = admin_user_id);

CREATE POLICY "Team updates restricted to admin"
  ON public.teams FOR UPDATE
  USING (auth.uid() = admin_user_id);

CREATE POLICY "Team delete restricted to admin"
  ON public.teams FOR DELETE
  USING (auth.uid() = admin_user_id);

GRANT SELECT ON public.teams TO authenticated;
GRANT ALL ON public.teams TO service_role;

CREATE TABLE IF NOT EXISTS public.user_tags (
  user_id UUID REFERENCES public.users(id) ON DELETE CASCADE,
  tag_id UUID REFERENCES public.tags(id) ON DELETE CASCADE,
  created_at TIMESTAMPTZ DEFAULT NOW(),
  PRIMARY KEY (user_id, tag_id)
);

ALTER TABLE public.user_tags ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Users manage their own tags"
  ON public.user_tags FOR ALL
  USING (auth.uid() = user_id)
  WITH CHECK (auth.uid() = user_id);

GRANT SELECT, INSERT, DELETE ON public.user_tags TO authenticated;
GRANT ALL ON public.user_tags TO service_role;

CREATE TABLE IF NOT EXISTS public.user_teams (
  user_id UUID REFERENCES public.users(id) ON DELETE CASCADE,
  team_id UUID REFERENCES public.teams(id) ON DELETE CASCADE,
  role TEXT NOT NULL DEFAULT 'member' CHECK (role IN ('member', 'admin', 'owner')),
  joined_at TIMESTAMPTZ DEFAULT NOW(),
  PRIMARY KEY (user_id, team_id)
);

ALTER TABLE public.user_teams ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Users can view their team memberships"
  ON public.user_teams FOR SELECT
  USING (
    user_id = auth.uid()
    OR EXISTS (
      SELECT 1 FROM public.teams t
      WHERE t.id = team_id AND t.admin_user_id = auth.uid()
    )
  );

CREATE POLICY "Users can join teams themselves"
  ON public.user_teams FOR INSERT
  WITH CHECK (user_id = auth.uid());

CREATE POLICY "Team admins can manage memberships"
  ON public.user_teams FOR ALL
  USING (
    EXISTS (
      SELECT 1 FROM public.teams t
      WHERE t.id = team_id AND t.admin_user_id = auth.uid()
    )
  )
  WITH CHECK (
    EXISTS (
      SELECT 1 FROM public.teams t
      WHERE t.id = team_id AND t.admin_user_id = auth.uid()
    )
  );

GRANT SELECT, INSERT, DELETE ON public.user_teams TO authenticated;
GRANT ALL ON public.user_teams TO service_role;

CREATE TABLE IF NOT EXISTS public.team_tags (
  team_id UUID REFERENCES public.teams(id) ON DELETE CASCADE,
  tag_id UUID REFERENCES public.tags(id) ON DELETE CASCADE,
  created_at TIMESTAMPTZ DEFAULT NOW(),
  PRIMARY KEY (team_id, tag_id)
);

ALTER TABLE public.team_tags ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Team tags readable by team members"
  ON public.team_tags FOR SELECT
  USING (
    EXISTS (
      SELECT 1 FROM public.user_teams ut
      WHERE ut.team_id = team_id AND ut.user_id = auth.uid()
    )
    OR EXISTS (
      SELECT 1 FROM public.teams t
      WHERE t.id = team_id AND t.admin_user_id = auth.uid()
    )
  );

CREATE POLICY "Team tags managed by team admin"
  ON public.team_tags FOR ALL
  USING (
    EXISTS (
      SELECT 1 FROM public.teams t
      WHERE t.id = team_id AND t.admin_user_id = auth.uid()
    )
  )
  WITH CHECK (
    EXISTS (
      SELECT 1 FROM public.teams t
      WHERE t.id = team_id AND t.admin_user_id = auth.uid()
    )
  );

GRANT SELECT ON public.team_tags TO authenticated;
GRANT ALL ON public.team_tags TO service_role;

-- Indexes for common lookups
CREATE INDEX IF NOT EXISTS idx_institutions_name ON public.institutions (name);
CREATE INDEX IF NOT EXISTS idx_tags_name ON public.tags (name);
CREATE INDEX IF NOT EXISTS idx_teams_admin_user_id ON public.teams (admin_user_id);
CREATE INDEX IF NOT EXISTS idx_user_tags_user ON public.user_tags (user_id);
CREATE INDEX IF NOT EXISTS idx_team_tags_team ON public.team_tags (team_id);
CREATE INDEX IF NOT EXISTS idx_user_teams_user ON public.user_teams (user_id);
CREATE INDEX IF NOT EXISTS idx_user_teams_team ON public.user_teams (team_id);
CREATE INDEX IF NOT EXISTS idx_users_institution_id ON public.users (institution_id);

-- Create a function to handle updated_at timestamps
CREATE OR REPLACE FUNCTION public.handle_updated_at()
RETURNS TRIGGER AS $$
BEGIN
  NEW.updated_at = NOW();
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Create triggers for updated_at
DROP TRIGGER IF EXISTS set_updated_at ON public.user_profiles;
CREATE TRIGGER set_updated_at
  BEFORE UPDATE ON public.user_profiles
  FOR EACH ROW
  EXECUTE FUNCTION public.handle_updated_at();

DROP TRIGGER IF EXISTS set_updated_at ON public.tarxiv_user_data;
CREATE TRIGGER set_updated_at
  BEFORE UPDATE ON public.tarxiv_user_data
  FOR EACH ROW
  EXECUTE FUNCTION public.handle_updated_at();

DROP TRIGGER IF EXISTS set_updated_at ON public.users;
CREATE TRIGGER set_updated_at
  BEFORE UPDATE ON public.users
  FOR EACH ROW
  EXECUTE FUNCTION public.handle_updated_at();

DROP TRIGGER IF EXISTS set_updated_at ON public.institutions;
CREATE TRIGGER set_updated_at
  BEFORE UPDATE ON public.institutions
  FOR EACH ROW
  EXECUTE FUNCTION public.handle_updated_at();

DROP TRIGGER IF EXISTS set_updated_at ON public.tags;
CREATE TRIGGER set_updated_at
  BEFORE UPDATE ON public.tags
  FOR EACH ROW
  EXECUTE FUNCTION public.handle_updated_at();

DROP TRIGGER IF EXISTS set_updated_at ON public.teams;
CREATE TRIGGER set_updated_at
  BEFORE UPDATE ON public.teams
  FOR EACH ROW
  EXECUTE FUNCTION public.handle_updated_at();
