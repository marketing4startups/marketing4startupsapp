BEGIN;
SELECT plan(1);

-- Examples: https://pgtap.org/documentation.html

SELECT * FROM finish();
ROLLBACK;
BEGIN;
SELECT plan(25);

SELECT ok((SELECT relrowsecurity FROM pg_class WHERE oid = 'public.profiles'::regclass), 'profiles has RLS enabled');
SELECT ok((SELECT relforcerowsecurity FROM pg_class WHERE oid = 'public.profiles'::regclass), 'profiles forces RLS');
SELECT ok((SELECT relrowsecurity FROM pg_class WHERE oid = 'public.workspaces'::regclass), 'workspaces has RLS enabled');
SELECT ok((SELECT relforcerowsecurity FROM pg_class WHERE oid = 'public.workspaces'::regclass), 'workspaces forces RLS');
SELECT ok((SELECT relrowsecurity FROM pg_class WHERE oid = 'public.workspace_members'::regclass), 'memberships has RLS enabled');
SELECT ok((SELECT relforcerowsecurity FROM pg_class WHERE oid = 'public.workspace_members'::regclass), 'memberships forces RLS');
SELECT ok((SELECT relrowsecurity FROM pg_class WHERE oid = 'public.startup_profiles'::regclass), 'startup profiles has RLS enabled');
SELECT ok((SELECT relforcerowsecurity FROM pg_class WHERE oid = 'public.startup_profiles'::regclass), 'startup profiles forces RLS');
SELECT ok((SELECT relrowsecurity FROM pg_class WHERE oid = 'public.experiments'::regclass), 'experiments has RLS enabled');
SELECT ok((SELECT relforcerowsecurity FROM pg_class WHERE oid = 'public.experiments'::regclass), 'experiments forces RLS');
SELECT ok((SELECT relrowsecurity FROM pg_class WHERE oid = 'public.customer_interviews'::regclass), 'interviews has RLS enabled');
SELECT ok((SELECT relforcerowsecurity FROM pg_class WHERE oid = 'public.customer_interviews'::regclass), 'interviews forces RLS');

SELECT ok(NOT has_table_privilege('anon', 'public.profiles', 'SELECT'), 'anon cannot read profiles');
SELECT ok(NOT has_table_privilege('anon', 'public.workspaces', 'SELECT'), 'anon cannot read workspaces');
SELECT ok(NOT has_table_privilege('anon', 'public.workspace_members', 'SELECT'), 'anon cannot read memberships');
SELECT ok(NOT has_table_privilege('anon', 'public.startup_profiles', 'SELECT'), 'anon cannot read startup profiles');
SELECT ok(NOT has_table_privilege('anon', 'public.experiments', 'SELECT'), 'anon cannot read experiments');
SELECT ok(NOT has_table_privilege('anon', 'public.customer_interviews', 'SELECT'), 'anon cannot read interviews');

SELECT ok(has_table_privilege('authenticated', 'public.profiles', 'SELECT'), 'authenticated can read permitted profiles');
SELECT ok(has_table_privilege('authenticated', 'public.workspaces', 'SELECT'), 'authenticated can read permitted workspaces');
SELECT ok(NOT has_table_privilege('authenticated', 'public.workspace_members', 'DELETE'), 'memberships cannot be deleted through Data API');
SELECT ok(NOT has_table_privilege('authenticated', 'public.startup_profiles', 'DELETE'), 'startup profiles cannot be deleted through Data API');
SELECT ok(NOT has_table_privilege('authenticated', 'public.profiles', 'DELETE'), 'profiles cannot be deleted through Data API');
SELECT ok(has_function_privilege('authenticated', 'public.initialize_account(text,text)', 'EXECUTE'), 'authenticated can initialize an account');
SELECT ok(NOT has_function_privilege('anon', 'public.initialize_account(text,text)', 'EXECUTE'), 'anon cannot initialize an account');

SELECT * FROM finish();
ROLLBACK;
