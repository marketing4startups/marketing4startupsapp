-- Supabase Auth owns credentials and sessions. This migration stores app data only.
CREATE SCHEMA IF NOT EXISTS app_private;
REVOKE ALL ON SCHEMA app_private FROM PUBLIC, anon, authenticated, service_role;

CREATE TABLE public.profiles (
  id uuid PRIMARY KEY REFERENCES auth.users(id) ON DELETE CASCADE,
  display_name text NOT NULL DEFAULT '' CHECK (char_length(display_name) <= 120),
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE public.workspaces (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  name text NOT NULL CHECK (char_length(name) BETWEEN 1 AND 160),
  created_by uuid NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
  created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE public.workspace_members (
  workspace_id uuid NOT NULL REFERENCES public.workspaces(id) ON DELETE CASCADE,
  user_id uuid NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
  role text NOT NULL DEFAULT 'owner' CHECK (role IN ('owner', 'admin', 'member')),
  joined_at timestamptz NOT NULL DEFAULT now(),
  PRIMARY KEY (workspace_id, user_id)
);

CREATE TABLE public.startup_profiles (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  workspace_id uuid NOT NULL UNIQUE REFERENCES public.workspaces(id) ON DELETE CASCADE,
  startup_stage text NOT NULL DEFAULT '',
  best_fit_customer text NOT NULL DEFAULT '',
  customer_pain text NOT NULL DEFAULT '',
  current_alternative text NOT NULL DEFAULT '',
  differentiator text NOT NULL DEFAULT '',
  customer_value text NOT NULL DEFAULT '',
  market_category text NOT NULL DEFAULT '',
  monthly_revenue_per_customer numeric(14,2) CHECK (monthly_revenue_per_customer IS NULL OR monthly_revenue_per_customer >= 0),
  gross_margin_percent numeric(5,2) CHECK (gross_margin_percent IS NULL OR gross_margin_percent BETWEEN 0 AND 100),
  cac_limit numeric(14,2) CHECK (cac_limit IS NULL OR cac_limit >= 0),
  monthly_churn_percent numeric(5,2) CHECK (monthly_churn_percent IS NULL OR monthly_churn_percent BETWEEN 0 AND 100),
  payback_months numeric(8,2) CHECK (payback_months IS NULL OR payback_months >= 0),
  ltv_cac_target numeric(8,2) CHECK (ltv_cac_target IS NULL OR ltv_cac_target >= 0),
  channel_candidates jsonb NOT NULL DEFAULT '[]'::jsonb CHECK (jsonb_typeof(channel_candidates) = 'array'),
  completed_at timestamptz,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE public.experiments (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  workspace_id uuid NOT NULL REFERENCES public.workspaces(id) ON DELETE CASCADE,
  created_by uuid NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
  name text NOT NULL CHECK (char_length(name) BETWEEN 1 AND 200),
  channel text NOT NULL DEFAULT '',
  status text NOT NULL DEFAULT 'Idea' CHECK (status IN ('Idea', 'Running', 'Check results', 'Complete')),
  hypothesis text NOT NULL DEFAULT '',
  cost_limit numeric(14,2) CHECK (cost_limit IS NULL OR cost_limit >= 0),
  review_date date,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE public.customer_interviews (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  workspace_id uuid NOT NULL REFERENCES public.workspaces(id) ON DELETE CASCADE,
  created_by uuid NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
  recent_event text NOT NULL,
  commitment text NOT NULL DEFAULT 'None yet',
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX workspace_members_user_idx ON public.workspace_members(user_id, workspace_id);
CREATE INDEX workspaces_creator_idx ON public.workspaces(created_by);
CREATE INDEX experiments_workspace_created_idx ON public.experiments(workspace_id, created_at DESC);
CREATE INDEX experiments_creator_idx ON public.experiments(created_by);
CREATE INDEX interviews_workspace_created_idx ON public.customer_interviews(workspace_id, created_at DESC);
CREATE INDEX interviews_creator_idx ON public.customer_interviews(created_by);

-- Updated-at trigger function is private and invoker-rights.
CREATE FUNCTION app_private.set_updated_at()
RETURNS trigger LANGUAGE plpgsql SECURITY INVOKER SET search_path = '' AS $$
BEGIN
  NEW.updated_at := now();
  RETURN NEW;
END;
$$;
REVOKE ALL ON FUNCTION app_private.set_updated_at() FROM PUBLIC, anon, authenticated, service_role;
CREATE TRIGGER profiles_set_updated_at BEFORE UPDATE ON public.profiles FOR EACH ROW EXECUTE FUNCTION app_private.set_updated_at();
CREATE TRIGGER startup_profiles_set_updated_at BEFORE UPDATE ON public.startup_profiles FOR EACH ROW EXECUTE FUNCTION app_private.set_updated_at();
CREATE TRIGGER experiments_set_updated_at BEFORE UPDATE ON public.experiments FOR EACH ROW EXECUTE FUNCTION app_private.set_updated_at();
CREATE TRIGGER interviews_set_updated_at BEFORE UPDATE ON public.customer_interviews FOR EACH ROW EXECUTE FUNCTION app_private.set_updated_at();

-- RLS plus explicit grants: a JWT must identify the user whose rows it can access.
ALTER TABLE public.profiles ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.workspaces ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.workspace_members ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.startup_profiles ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.experiments ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.customer_interviews ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.profiles FORCE ROW LEVEL SECURITY;
ALTER TABLE public.workspaces FORCE ROW LEVEL SECURITY;
ALTER TABLE public.workspace_members FORCE ROW LEVEL SECURITY;
ALTER TABLE public.startup_profiles FORCE ROW LEVEL SECURITY;
ALTER TABLE public.experiments FORCE ROW LEVEL SECURITY;
ALTER TABLE public.customer_interviews FORCE ROW LEVEL SECURITY;

REVOKE ALL ON public.profiles, public.workspaces, public.workspace_members,
  public.startup_profiles, public.experiments, public.customer_interviews FROM PUBLIC, anon, authenticated;
GRANT SELECT, INSERT ON public.profiles TO authenticated;
GRANT UPDATE (display_name) ON public.profiles TO authenticated;
GRANT SELECT, INSERT ON public.workspaces TO authenticated;
GRANT UPDATE (name) ON public.workspaces TO authenticated;
GRANT SELECT, INSERT ON public.workspace_members TO authenticated;
GRANT SELECT, INSERT ON public.startup_profiles TO authenticated;
GRANT UPDATE (startup_stage, best_fit_customer, customer_pain, current_alternative, differentiator,
  customer_value, market_category, monthly_revenue_per_customer, gross_margin_percent, cac_limit,
  monthly_churn_percent, payback_months, ltv_cac_target, channel_candidates, completed_at)
  ON public.startup_profiles TO authenticated;
GRANT SELECT, INSERT, DELETE ON public.experiments TO authenticated;
GRANT UPDATE (name, channel, status, hypothesis, cost_limit, review_date) ON public.experiments TO authenticated;
GRANT SELECT, INSERT, DELETE ON public.customer_interviews TO authenticated;
GRANT UPDATE (recent_event, commitment) ON public.customer_interviews TO authenticated;

CREATE POLICY profiles_select_self ON public.profiles FOR SELECT TO authenticated USING (id = (SELECT auth.uid()));
CREATE POLICY profiles_insert_self ON public.profiles FOR INSERT TO authenticated WITH CHECK (id = (SELECT auth.uid()));
CREATE POLICY profiles_update_self ON public.profiles FOR UPDATE TO authenticated
  USING (id = (SELECT auth.uid())) WITH CHECK (id = (SELECT auth.uid()));

CREATE POLICY workspaces_select_member ON public.workspaces FOR SELECT TO authenticated
  USING (workspaces.created_by = (SELECT auth.uid()) OR EXISTS (
    SELECT 1 FROM public.workspace_members m WHERE m.workspace_id = workspaces.id AND m.user_id = (SELECT auth.uid())
  ));
CREATE POLICY workspaces_insert_self ON public.workspaces FOR INSERT TO authenticated
  WITH CHECK (workspaces.created_by = (SELECT auth.uid()));
CREATE POLICY workspaces_update_admin ON public.workspaces FOR UPDATE TO authenticated
  USING (EXISTS (SELECT 1 FROM public.workspace_members m WHERE m.workspace_id = workspaces.id
    AND m.user_id = (SELECT auth.uid()) AND m.role IN ('owner', 'admin')))
  WITH CHECK (EXISTS (SELECT 1 FROM public.workspace_members m WHERE m.workspace_id = workspaces.id
    AND m.user_id = (SELECT auth.uid()) AND m.role IN ('owner', 'admin')));

CREATE POLICY workspace_members_select_self ON public.workspace_members FOR SELECT TO authenticated
  USING (user_id = (SELECT auth.uid()));
CREATE POLICY workspace_members_insert_owner ON public.workspace_members FOR INSERT TO authenticated
  WITH CHECK (workspace_members.user_id = (SELECT auth.uid()) AND workspace_members.role = 'owner' AND EXISTS (
    SELECT 1 FROM public.workspaces w WHERE w.id = workspace_members.workspace_id AND w.created_by = (SELECT auth.uid())
  ));

CREATE POLICY startup_profiles_select_member ON public.startup_profiles FOR SELECT TO authenticated
  USING (EXISTS (SELECT 1 FROM public.workspace_members m WHERE m.workspace_id = startup_profiles.workspace_id AND m.user_id = (SELECT auth.uid())));
CREATE POLICY startup_profiles_insert_admin ON public.startup_profiles FOR INSERT TO authenticated
  WITH CHECK (EXISTS (SELECT 1 FROM public.workspace_members m WHERE m.workspace_id = startup_profiles.workspace_id
    AND m.user_id = (SELECT auth.uid()) AND m.role IN ('owner', 'admin')));
CREATE POLICY startup_profiles_update_admin ON public.startup_profiles FOR UPDATE TO authenticated
  USING (EXISTS (SELECT 1 FROM public.workspace_members m WHERE m.workspace_id = startup_profiles.workspace_id
    AND m.user_id = (SELECT auth.uid()) AND m.role IN ('owner', 'admin')))
  WITH CHECK (EXISTS (SELECT 1 FROM public.workspace_members m WHERE m.workspace_id = startup_profiles.workspace_id
    AND m.user_id = (SELECT auth.uid()) AND m.role IN ('owner', 'admin')));

CREATE POLICY experiments_select_member ON public.experiments FOR SELECT TO authenticated
  USING (EXISTS (SELECT 1 FROM public.workspace_members m WHERE m.workspace_id = experiments.workspace_id AND m.user_id = (SELECT auth.uid())));
CREATE POLICY experiments_insert_member ON public.experiments FOR INSERT TO authenticated
  WITH CHECK (experiments.created_by = (SELECT auth.uid()) AND EXISTS (SELECT 1 FROM public.workspace_members m
    WHERE m.workspace_id = experiments.workspace_id AND m.user_id = (SELECT auth.uid())));
CREATE POLICY experiments_update_member ON public.experiments FOR UPDATE TO authenticated
  USING ((experiments.created_by = (SELECT auth.uid()) OR EXISTS (SELECT 1 FROM public.workspace_members m
    WHERE m.workspace_id = experiments.workspace_id AND m.user_id = (SELECT auth.uid()) AND m.role IN ('owner', 'admin')))
    AND EXISTS (SELECT 1 FROM public.workspace_members m WHERE m.workspace_id = experiments.workspace_id AND m.user_id = (SELECT auth.uid())))
  WITH CHECK ((experiments.created_by = (SELECT auth.uid()) OR EXISTS (SELECT 1 FROM public.workspace_members m
    WHERE m.workspace_id = experiments.workspace_id AND m.user_id = (SELECT auth.uid()) AND m.role IN ('owner', 'admin')))
    AND EXISTS (SELECT 1 FROM public.workspace_members m WHERE m.workspace_id = experiments.workspace_id AND m.user_id = (SELECT auth.uid())));
CREATE POLICY experiments_delete_member ON public.experiments FOR DELETE TO authenticated
  USING ((experiments.created_by = (SELECT auth.uid()) OR EXISTS (SELECT 1 FROM public.workspace_members m
    WHERE m.workspace_id = experiments.workspace_id AND m.user_id = (SELECT auth.uid()) AND m.role IN ('owner', 'admin')))
    AND EXISTS (SELECT 1 FROM public.workspace_members m WHERE m.workspace_id = experiments.workspace_id AND m.user_id = (SELECT auth.uid())));

CREATE POLICY interviews_select_member ON public.customer_interviews FOR SELECT TO authenticated
  USING (EXISTS (SELECT 1 FROM public.workspace_members m WHERE m.workspace_id = customer_interviews.workspace_id AND m.user_id = (SELECT auth.uid())));
CREATE POLICY interviews_insert_member ON public.customer_interviews FOR INSERT TO authenticated
  WITH CHECK (customer_interviews.created_by = (SELECT auth.uid()) AND EXISTS (SELECT 1 FROM public.workspace_members m
    WHERE m.workspace_id = customer_interviews.workspace_id AND m.user_id = (SELECT auth.uid())));
CREATE POLICY interviews_update_member ON public.customer_interviews FOR UPDATE TO authenticated
  USING ((customer_interviews.created_by = (SELECT auth.uid()) OR EXISTS (SELECT 1 FROM public.workspace_members m
    WHERE m.workspace_id = customer_interviews.workspace_id AND m.user_id = (SELECT auth.uid()) AND m.role IN ('owner', 'admin')))
    AND EXISTS (SELECT 1 FROM public.workspace_members m WHERE m.workspace_id = customer_interviews.workspace_id AND m.user_id = (SELECT auth.uid())))
  WITH CHECK ((customer_interviews.created_by = (SELECT auth.uid()) OR EXISTS (SELECT 1 FROM public.workspace_members m
    WHERE m.workspace_id = customer_interviews.workspace_id AND m.user_id = (SELECT auth.uid()) AND m.role IN ('owner', 'admin')))
    AND EXISTS (SELECT 1 FROM public.workspace_members m WHERE m.workspace_id = customer_interviews.workspace_id AND m.user_id = (SELECT auth.uid())));
CREATE POLICY interviews_delete_member ON public.customer_interviews FOR DELETE TO authenticated
  USING ((customer_interviews.created_by = (SELECT auth.uid()) OR EXISTS (SELECT 1 FROM public.workspace_members m
    WHERE m.workspace_id = customer_interviews.workspace_id AND m.user_id = (SELECT auth.uid()) AND m.role IN ('owner', 'admin')))
    AND EXISTS (SELECT 1 FROM public.workspace_members m WHERE m.workspace_id = customer_interviews.workspace_id AND m.user_id = (SELECT auth.uid())));

-- One atomic, authenticated onboarding call creates the app-side account records.
CREATE FUNCTION public.initialize_account(workspace_name text, display_name text DEFAULT '')
RETURNS uuid LANGUAGE plpgsql SECURITY INVOKER SET search_path = '' AS $$
DECLARE
  caller uuid := (SELECT auth.uid());
  new_workspace uuid;
BEGIN
  IF caller IS NULL THEN RAISE EXCEPTION 'Authentication required' USING ERRCODE = '28000'; END IF;
  IF char_length(btrim(workspace_name)) NOT BETWEEN 1 AND 160 THEN
    RAISE EXCEPTION 'Workspace name must be 1 to 160 characters' USING ERRCODE = '22023';
  END IF;
  INSERT INTO public.profiles(id, display_name) VALUES (caller, coalesce(display_name, ''))
    ON CONFLICT (id) DO NOTHING;
  SELECT id INTO new_workspace FROM public.workspaces WHERE created_by = caller ORDER BY created_at LIMIT 1;
  IF new_workspace IS NULL THEN
    INSERT INTO public.workspaces(name, created_by) VALUES (btrim(workspace_name), caller) RETURNING id INTO new_workspace;
    INSERT INTO public.workspace_members(workspace_id, user_id, role) VALUES (new_workspace, caller, 'owner');
    INSERT INTO public.startup_profiles(workspace_id) VALUES (new_workspace);
  END IF;
  INSERT INTO public.workspace_members(workspace_id, user_id, role) VALUES (new_workspace, caller, 'owner')
    ON CONFLICT (workspace_id, user_id) DO NOTHING;
  INSERT INTO public.startup_profiles(workspace_id) VALUES (new_workspace)
    ON CONFLICT (workspace_id) DO NOTHING;
  RETURN new_workspace;
END;
$$;
REVOKE ALL ON FUNCTION public.initialize_account(text, text) FROM PUBLIC, anon, authenticated;
GRANT EXECUTE ON FUNCTION public.initialize_account(text, text) TO authenticated;

