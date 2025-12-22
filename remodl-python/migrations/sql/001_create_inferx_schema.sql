-- Migration: Create InferX schema and tables for StateSvc
-- Date: 2025-12-22
-- Description: Creates inferx schema and all necessary tables for tenant, namespace, function, and node management

-- Create schema
CREATE SCHEMA IF NOT EXISTS inferx;

-- Set search path
SET search_path TO inferx;

-- ==================== Tenants ====================

CREATE TABLE IF NOT EXISTS tenants (
    name VARCHAR PRIMARY KEY,
    spec JSONB NOT NULL DEFAULT '{}',
    disabled BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_tenants_disabled ON tenants(disabled);

-- ==================== Namespaces ====================

CREATE TABLE IF NOT EXISTS namespaces (
    tenant VARCHAR NOT NULL,
    name VARCHAR NOT NULL,
    spec JSONB NOT NULL DEFAULT '{}',
    disabled BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    PRIMARY KEY (tenant, name)
);

CREATE INDEX IF NOT EXISTS idx_namespaces_tenant ON namespaces(tenant);
CREATE INDEX IF NOT EXISTS idx_namespaces_disabled ON namespaces(disabled);

-- ==================== Functions ====================

CREATE TABLE IF NOT EXISTS functions (
    tenant VARCHAR NOT NULL,
    namespace VARCHAR NOT NULL,
    name VARCHAR NOT NULL,
    version BIGINT NOT NULL,
    spec JSONB NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    PRIMARY KEY (tenant, namespace, name, version)
);

CREATE INDEX IF NOT EXISTS idx_functions_tenant_namespace ON functions(tenant, namespace);
CREATE INDEX IF NOT EXISTS idx_functions_name ON functions(name);
CREATE INDEX IF NOT EXISTS idx_functions_version ON functions(version);

-- ==================== Function Status ====================

CREATE TABLE IF NOT EXISTS function_status (
    tenant VARCHAR NOT NULL,
    namespace VARCHAR NOT NULL,
    name VARCHAR NOT NULL,
    version BIGINT NOT NULL,
    state VARCHAR NOT NULL DEFAULT 'Normal',
    snapshoting_failure_cnt INTEGER DEFAULT 0,
    resuming_failure_cnt INTEGER DEFAULT 0,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    PRIMARY KEY (tenant, namespace, name, version)
);

CREATE INDEX IF NOT EXISTS idx_function_status_state ON function_status(state);

-- ==================== Nodes ====================

CREATE TABLE IF NOT EXISTS nodes (
    name VARCHAR PRIMARY KEY,
    node_ip VARCHAR NOT NULL,
    na_ip VARCHAR NOT NULL,
    agent_url VARCHAR NOT NULL,
    spec JSONB NOT NULL,
    state VARCHAR DEFAULT 'NodeAgentAvaiable',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_nodes_state ON nodes(state);
CREATE INDEX IF NOT EXISTS idx_nodes_updated ON nodes(updated_at);

-- ==================== User Roles (if not exists in public schema) ====================

-- Note: userrole table already exists in secret-db public schema
-- This creates it in inferx schema for consistency if needed
CREATE TABLE IF NOT EXISTS userrole (
    username VARCHAR NOT NULL,
    rolename VARCHAR NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    PRIMARY KEY (username, rolename)
);

CREATE INDEX IF NOT EXISTS idx_userrole_rolename ON userrole(rolename);
CREATE INDEX IF NOT EXISTS idx_userrole_username ON userrole(username);

-- ==================== API Keys (if needed) ====================

CREATE TABLE IF NOT EXISTS apikey (
    key VARCHAR PRIMARY KEY,
    username VARCHAR NOT NULL,
    description VARCHAR,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    expires_at TIMESTAMP WITH TIME ZONE,
    last_used_at TIMESTAMP WITH TIME ZONE
);

CREATE INDEX IF NOT EXISTS idx_apikey_username ON apikey(username);
CREATE INDEX IF NOT EXISTS idx_apikey_expires ON apikey(expires_at) WHERE expires_at IS NOT NULL;

-- ==================== Comments ====================

COMMENT ON SCHEMA inferx IS 'InferX state management schema - separate from LiteLLM tables';
COMMENT ON TABLE tenants IS 'InferX tenants (e.g., public, remodl, inferx)';
COMMENT ON TABLE namespaces IS 'InferX namespaces within tenants';
COMMENT ON TABLE functions IS 'Model deployment specifications';
COMMENT ON TABLE function_status IS 'Function deployment status tracking';
COMMENT ON TABLE nodes IS 'GPU worker node registrations';
COMMENT ON TABLE userrole IS 'User role assignments for tenant/namespace access';
COMMENT ON TABLE apikey IS 'API keys for authentication';
