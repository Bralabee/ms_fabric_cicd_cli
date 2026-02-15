# Blueprint Template Catalog

This document provides a comprehensive guide to all available blueprint templates in the `usf_fabric_cli_cicd` framework. Each template is production-ready and optimized for specific use cases.

## Quick Reference Table

| Template | Best For | Complexity | Estimated Cost/Month | Min Capacity |
|----------|----------|------------|----------------------|--------------|
| [minimal_starter](#1-minimal-starter) | Learning, POCs, Solo projects | ★☆☆☆☆ | $0-100 | F2 (Trial) |
| [basic_etl](#2-basic-etl) | Standard ETL pipelines | ★★☆☆☆ | $100-500 | F8 |
| [advanced_analytics](#3-advanced-analytics) | ML/AI workloads | ★★★☆☆ | $500-1500 | F16 |
| [data_science](#4-data-science) | Research & experimentation | ★★☆☆☆ | $200-800 | F8 |
| [extensive_example](#5-extensive-example) | Enterprise reference | ★★★★☆ | $1000-3000 | F32 |
| [medallion](#6-medallion) | Medallion Architecture (Bronze/Silver/Gold) | ★★★☆☆ | $300-1200 | F8 |
| [realtime_streaming](#7-realtime-streaming) | IoT, events, real-time | ★★★★☆ | $800-2500 | F16 |
| [compliance_regulated](#8-compliance-regulated) | Healthcare, Finance, Gov | ★★★★★ | $1500-5000 | F16 |
| [data_mesh_domain](#9-data-mesh-domain) | Domain-driven orgs | ★★★★☆ | $500-2000 | F16 |
| [migration_hybrid](#10-migration-hybrid) | Cloud migration projects | ★★★★☆ | $1000-5000 | F16 |
| [specialized_timeseries](#11-specialized-timeseries) | Time-series, APM, logs | ★★★★☆ | $1000-5000 | F16 |

---

## 1. Minimal Starter

**File:** `src/usf_fabric_cli/templates/blueprints/minimal_starter.yaml`

### Overview

The absolute minimum viable Fabric workspace for quick prototyping and learning.

### Key Features

- ✅ Single lakehouse (all-in-one data storage)
- ✅ Single notebook (clear entry point)
- ✅ Optional pipeline (basic ETL)
- ✅ No Git integration (simplicity first)
- ✅ Minimal principals (just deploying service principal)

### Use Cases

- Learning Microsoft Fabric
- Individual contributor projects
- Proof-of-concept development
- Training environments
- Quick data exploration

### Resource Footprint

- **Items:** 1 lakehouse, 1 notebook, 1 pipeline
- **Cost:** $0/month (F2 trial) or $50-100/month (F8)
- **Capacity:** F2 minimum

### Getting Started

```bash
python -m usf_fabric_cli.scripts.dev.generate_project "My Company" "Quick POC" \
  --template minimal_starter \
  --capacity-id F2

# Deploy
make deploy config=config/projects/my_company/quick_poc.yaml env=dev
```

### When to Graduate

Move to `basic_etl` when you need:

- Git version control
- Multiple data zones (Bronze/Silver/Gold)
- Team collaboration features

---

## 2. Basic ETL

**File:** `src/usf_fabric_cli/templates/blueprints/basic_etl.yaml`

### Overview

Standard medallion architecture (Bronze → Silver → Gold) for production ETL pipelines.

### Key Features

- ✅ Medallion architecture (Bronze/Silver/Gold)
- ✅ Lakehouses for each layer
- ✅ Data warehouse for reporting
- ✅ Git integration for version control
- ✅ Team collaboration (RBAC)

### Use Cases

- Standard ETL workflows
- Batch data processing
- Data lake modernization
- Team-based development

### Resource Footprint

- **Items:** 3 lakehouses, 1 warehouse, 3 notebooks, 2 pipelines, 1 semantic model
- **Cost:** $100-500/month (F8-F16)
- **Capacity:** F8 minimum

### Getting Started

```bash
python -m usf_fabric_cli.scripts.dev.generate_project "Acme Corp" "Sales Analytics" \
  --template basic_etl \
  --git-repo "https://dev.azure.com/acme/FabricProjects/_git/sales"

make deploy config=config/projects/acme_corp/sales_analytics.yaml env=dev
```

---

## 3. Advanced Analytics

**File:** `src/usf_fabric_cli/templates/blueprints/advanced_analytics.yaml`

### Overview

ML/AI-focused workspace with feature stores, model training, and MLOps.

### Key Features

- ✅ Feature store integration
- ✅ ML model training environments
- ✅ Model serving infrastructure
- ✅ Experiment tracking
- ✅ A/B testing support

### Use Cases

- Machine learning projects
- Predictive analytics
- Feature engineering
- Model deployment and serving

### Resource Footprint

- **Items:** 4 lakehouses, 1 warehouse, 8 notebooks, 3 pipelines
- **Cost:** $500-1500/month (F16-F32)
- **Capacity:** F16 minimum

---

## 4. Data Science

**File:** `src/usf_fabric_cli/templates/blueprints/data_science.yaml`

### Overview

Research-oriented workspace for exploratory analysis and experimentation.

### Key Features

- ✅ Jupyter-style environments
- ✅ Research data storage
- ✅ Experiment notebooks
- ✅ Minimal ETL overhead

### Use Cases

- Research projects
- Ad-hoc analysis
- Data exploration
- Academic work

---

## 5. Extensive Example

**File:** `src/usf_fabric_cli/templates/blueprints/extensive_example.yaml`

### Overview

Comprehensive reference implementation showcasing all framework capabilities.

### Key Features

- ✅ All artifact types demonstrated
- ✅ Git integration
- ✅ Advanced RBAC
- ✅ Eventstreams and KQL databases
- ✅ Full documentation

### Use Cases

- Reference architecture
- Framework capability demonstration
- Training material
- Template customization base

---

## 6. Medallion

**File:** `src/usf_fabric_cli/templates/blueprints/medallion.yaml`

### Overview

Industry-standard Medallion Architecture (Bronze → Silver → Gold) for scalable data engineering with clear data lineage and auditability.

### Key Features

- ✅ **Three-tier data architecture** (Bronze/Silver/Gold lakehouses)
- ✅ **Serving warehouse** (SQL-accessible Gold layer)
- ✅ **Transformation notebooks** (ingestion, quality checks, aggregation)
- ✅ **Orchestration pipeline** (daily refresh)
- ✅ **Full RBAC** (admin, contributor, viewer, CI/CD service principal)
- ✅ **Environment overrides** (dev/test/prod with separate capacities)
- ✅ **Git integration** ready

### Use Cases

- Scalable data engineering foundations
- Enterprise data lakehouse platforms
- Clear data lineage and auditability requirements
- Transform to medallion architecture
- Standard Bronze/Silver/Gold processing pipelines

### Resource Footprint

- **Items:** 3 lakehouses, 1 warehouse, 3 notebooks, 1 pipeline, 6 principals
- **Cost:** $300-1200/month (F8-F16)
- **Capacity:** F8 minimum

### Layer Details

| Layer | Lakehouse | Purpose |
|-------|-----------|---------|
| **Bronze** | `lh_bronze` | Raw data landing zone (immutable, append-only) |
| **Silver** | `lh_silver` | Cleaned, deduplicated, validated data |
| **Gold** | `lh_gold` | Star schema / dimensional models for reporting |

### Getting Started

```bash
python -m usf_fabric_cli.scripts.dev.generate_project "Acme Corp" "Sales Data" \
  --template medallion \
  --capacity-id ${FABRIC_CAPACITY_ID}

make deploy config=config/projects/acme_corp/sales_data.yaml env=dev
```

### Configuration Notes

- Each layer is isolated in its own Lakehouse (best practice)
- `wh_serving` provides a SQL-accessible endpoint for BI tools
- Use the `marketing_data_refresh` pipeline as a starting point for custom orchestration
- Environment overrides set separate capacity IDs for dev/test/prod

---

## 7. Real-Time Streaming

**File:** `src/usf_fabric_cli/templates/blueprints/realtime_streaming.yaml`

### Overview

High-throughput streaming platform with real-time analytics and alerting.

### Key Features

- ✅ **Eventstreams** for data ingestion (IoT, logs, clickstreams)
- ✅ **Eventhouse** for unified real-time analytics
- ✅ **KQL Databases** for sub-second queries
- ✅ **KQL Querysets** for reusable queries
- ✅ **Reflex** for event-driven automation
- ✅ **KQL Dashboards** for live monitoring
- ✅ Archival to lakehouse for long-term storage

### Use Cases

- IoT device telemetry (1M+ devices)
- Real-time log aggregation
- Clickstream analysis
- Monitoring and alerting systems
- Event-driven architectures

### Resource Footprint

- **Items:** 1 lakehouse, 3 eventstreams, 1 eventhouse, 2 KQL databases, 1 KQL queryset, 2 reflex, 1 KQL dashboard, 2 notebooks, 1 pipeline
- **Cost:** $800-2500/month (F16-F32)
- **Capacity:** F16 minimum (streaming workloads)

### Performance Characteristics

- **Ingestion:** 10k-100k events/second
- **Query Latency:** <100ms (point queries), <2s (1h range)
- **Retention:** 24h hot, 30d warm, 7y+ cold (lakehouse)

### Getting Started

```bash
python -m usf_fabric_cli.scripts.dev.generate_project "TechCorp" "IoT Platform" \
  --template realtime_streaming \
  --capacity-id F16

make deploy config=config/projects/techcorp/iot_platform.yaml env=dev
```

### Configuration Notes

- Eventstreams support: Event Hub, IoT Hub, Kafka, custom endpoints
- KQL provides 10-100x better performance than SQL for time-series data
- Reflex enables serverless event processing (no custom code needed)
- Use `streaming_archive` lakehouse for cost-effective long-term storage

---

## 8. Compliance-Regulated

**File:** `src/usf_fabric_cli/templates/blueprints/compliance_regulated.yaml`

### Overview

Enterprise-grade platform with strict security controls for regulated industries.

### Key Features

- ✅ **Classification-based folders** (Restricted/Confidential/Internal)
- ✅ **Separate lakehouses** by sensitivity level
- ✅ **Audit log repository** (immutable logs)
- ✅ **PII/PHI detection** and masking
- ✅ **Data lineage tracking**
- ✅ **Managed private endpoints** (network isolation)
- ✅ **Strict RBAC** with mandatory security/compliance team access
- ✅ **Compliance dashboard** for KPI reporting

### Use Cases

- Healthcare (HIPAA compliance)
- Financial services (SOC 2, PCI-DSS)
- Government (FedRAMP)
- Insurance (data privacy regulations)

### Resource Footprint

- **Items:** 3 lakehouses, 1 warehouse, 4 notebooks, 2 pipelines, 1 semantic model, 2 environments
- **Cost:** $1500-5000/month (F16-F64)
- **Capacity:** F16 minimum (enterprise security features)

### Security Principals

- **Mandatory:** Security admin group (Admin)
- **Mandatory:** Compliance officer group (Admin - audit rights)
- **Mandatory:** Audit service principal (automated logging)
- **Optional:** Data governance, engineers, analysts (graduated access)

### Compliance Checklist

After deployment, manually configure:

- ☐ Microsoft Purview integration
- ☐ Sensitivity labels on all items
- ☐ Audit logging (workspace + item level)
- ☐ Data retention policies (7y financial, 6y healthcare)
- ☐ Row-level security (RLS)
- ☐ Customer-managed keys (CMK)
- ☐ Private endpoints
- ☐ Multi-factor authentication (MFA)
- ☐ Weekly compliance scanning
- ☐ Data flow documentation
- ☐ PII masking (non-prod)
- ☐ Unauthorized access alerts

### Getting Started

```bash
python -m usf_fabric_cli.scripts.dev.generate_project "HealthCare Inc" "Patient Data Platform" \
  --template compliance_regulated \
  --capacity-id F16

# Review and update principals with actual Object IDs
vim config/projects/healthcare_inc/patient_data_platform.yaml

make deploy config=config/projects/healthcare_inc/patient_data_platform.yaml env=prod
```

### Legal Note

⚠️ **Legal review recommended** before production deployment in regulated industries.

---

## 9. Data Mesh Domain

**File:** `src/usf_fabric_cli/templates/blueprints/data_mesh_domain.yaml`

### Overview

Domain-driven data ownership with federated governance architecture.

### Key Features

- ✅ **Domain ownership** (decentralized data management)
- ✅ **Data products** (published datasets with SLAs)
- ✅ **GraphQL API** for self-service consumption
- ✅ **External data sharing** (cross-domain collaboration)
- ✅ **Mirrored databases** (avoid tight coupling)
- ✅ **Data contracts** with quality validation
- ✅ **Central governance** (viewer access for audit only)

### Use Cases

- Large enterprises with multiple business domains
- Organizations adopting data mesh principles
- Teams with decentralized data ownership
- Cross-functional data collaboration

### Data Mesh Principles

1. **Domain Ownership:** Each domain owns its workspace and data products
2. **Data as a Product:** Discoverable, addressable, self-describing datasets
3. **Self-Serve Platform:** GraphQL API enables autonomous consumption
4. **Federated Governance:** Central governance has audit access, not control

### Resource Footprint

- **Items:** 3 lakehouses, 1 warehouse, 1 semantic model, 3 notebooks, 2 pipelines, 1 GraphQL API, 1 external share, 1 mirrored database
- **Cost:** $500-2000/month per domain (F16-F32)
- **Capacity:** F16 minimum

### Domain Examples

Clone this template for each domain:

- **Sales Domain:** Sales metrics, customer insights
- **Customer Domain:** Customer master data, profiles
- **Product Domain:** Product catalog, inventory
- **Finance Domain:** Financial transactions, GL

### Cross-Domain Integration

- **Consumes:** Mirrored databases from other domains
- **Publishes:** Data products via GraphQL API
- **Governance:** Central team has viewer access for compliance

### Getting Started

```bash
# Create Sales domain workspace
python -m usf_fabric_cli.scripts.dev.generate_project "Enterprise Corp" "Sales Domain" \
  --template data_mesh_domain \
  --capacity-id F16

# Update domain-specific settings
vim config/projects/enterprise_corp/sales_domain.yaml
# Change: workspace.domain = "Sales"
# Update: published data products in Consumer/ folder
# Configure: cross-domain consumers in principals

make deploy config=config/projects/enterprise_corp/sales_domain.yaml env=prod
```

---

## 10. Migration & Hybrid

**File:** `src/usf_fabric_cli/templates/blueprints/migration_hybrid.yaml`

### Overview

Facilitates cloud migration with minimal disruption using hybrid architecture.

### Key Features

- ✅ **Mirrored databases** (real-time sync with on-prem SQL Server, Snowflake, Azure SQL)
- ✅ **On-premises gateway** integration
- ✅ **Dual environments** (legacy + modern side-by-side)
- ✅ **Data validation** (100% accuracy checks)
- ✅ **Phased migration** strategy (lift-shift → modernize → cutover)
- ✅ **Rollback capability** (<1 hour to revert)
- ✅ **Multi-cloud support** (AWS S3, Snowflake connectors)

### Use Cases

- Legacy system modernization
- SQL Server → Fabric migration
- Snowflake → Fabric migration
- On-premises → cloud migration
- Multi-cloud consolidation

### Migration Phases

**Phase 1: Lift & Shift (Weeks 1-4)**

- Mirror on-prem databases to Fabric
- Replicate legacy warehouse structure
- Parallel run: Legacy + Cloud
- Validate 100% data consistency

**Phase 2: Schema Modernization (Weeks 5-8)**

- Transform to medallion architecture
- Optimize for cloud performance
- Maintain backward compatibility
- Validate functional equivalence

**Phase 3: Cutover (Weeks 9-12)**

- Blue/Green deployment
- Redirect users to modern platform
- Keep legacy as fallback (2 weeks)
- Decommission legacy systems

**Phase 4: Optimization (Weeks 13-16)**

- Remove compatibility layers
- Optimize cloud-native performance
- Complete migration

### Resource Footprint

- **Items:** 3 lakehouses, 2 warehouses, 5 notebooks, 4 pipelines, 1 semantic model, 4 mirrored databases, 1 gateway, 3 connections
- **Cost:** $1000-5000/month during migration (dual environments), $500-2000/month post-migration
- **Capacity:** F16 minimum

### Rollback Plan

- MirroredDatabases enable instant rollback
- Dual-write during transition
- Data drift detection (every 15 min)
- Rollback SLA: <1 hour

### Getting Started

```bash
python -m usf_fabric_cli.scripts.dev.generate_project "Legacy Corp" "Cloud Migration" \
  --template migration_hybrid \
  --capacity-id F16

# Configure mirrored database connections
vim config/projects/legacy_corp/cloud_migration.yaml
# Update: MirroredDatabase resources with on-prem connection strings

# Prerequisites: Install on-premises gateway
# See: https://docs.microsoft.com/fabric/gateway

make deploy config=config/projects/legacy_corp/cloud_migration.yaml env=test
```

### Migration Checklist

- ☐ Install on-premises data gateway
- ☐ Configure VPN/ExpressRoute
- ☐ Set up mirrored database connections
- ☐ Establish baseline performance metrics
- ☐ Create data validation checksums
- ☐ Monitor replication lag (target: <5min)
- ☐ Document all dependencies
- ☐ Create communication plan
- ☐ Schedule migration windows
- ☐ Set up rollback procedures

---

## 11. Specialized Time-Series

**File:** `src/usf_fabric_cli/templates/blueprints/specialized_timeseries.yaml`

### Overview

High-performance platform for time-series data, IoT at scale, and operational intelligence.

### Key Features

- ✅ **KQL Databases** (optimized for time-series queries)
- ✅ **Eventhouse** (unified analytics engine)
- ✅ **Hot/Warm/Cold storage** (tiered retention)
- ✅ **Pre-computed aggregates** (1m, 5m, 1h, 1d rollups)
- ✅ **KQL Querysets** (reusable analytical queries)
- ✅ **Real-time dashboards** (auto-refresh: 30s)
- ✅ **Automated alerting** (threshold-based via Reflex)
- ✅ **MetricSets** (unified metrics catalog)

### Use Cases

- IoT fleet management (1M+ devices)
- Financial tick data (100k ticks/sec)
- Application Performance Monitoring (APM)
- Infrastructure monitoring
- Log aggregation (1TB+/day)
- Anomaly detection
- Capacity planning

### Resource Footprint

- **Items:** 1 lakehouse, 4 KQL databases, 1 eventhouse, 3 KQL querysets, 3 eventstreams, 3 KQL dashboards, 2 reflex, 4 notebooks, 3 pipelines, 2 metric sets
- **Cost:** $1000-5000/month (F16-F64)
- **Capacity:** F16 minimum (high-throughput workloads)

### Performance Targets

- **Point queries:** <100ms (single device/metric)
- **Range queries (1h):** <500ms
- **Range queries (24h):** <2 seconds
- **Range queries (30d):** <10 seconds
- **Historical queries (1y):** <60 seconds

### Data Retention Policy

- **Hot (RealTime KQL):** 24 hours (sub-second queries)
- **Warm (Recent KQL):** 30 days (1-2 second queries)
- **Cold (Lakehouse):** 7 years (batch queries)
- **Aggregates:** Indefinite (pre-computed rollups)

### Performance Optimizations

1. **Time-based partitioning** (hourly/daily)
2. **Materialized views** (common query patterns)
3. **Extent merging policies** (optimal file sizes)
4. **Ingestion batching** (10k events/sec)
5. **Query result caching**
6. **Sharding** (by device_id/metric_name)

### Getting Started

```bash
python -m usf_fabric_cli.scripts.dev.generate_project "Operations Inc" "Monitoring Platform" \
  --template specialized_timeseries \
  --capacity-id F16

make deploy config=config/projects/operations_inc/monitoring_platform.yaml env=prod
```

### KQL Query Examples

```kql
// Real-time anomaly detection
MetricsTable
| where Timestamp > ago(1h)
| summarize avg(Value), stdev(Value) by DeviceId, bin(Timestamp, 1m)
| where Value > avg_Value + 3*stdev_Value

// Capacity planning trend
MetricsTable
| where Timestamp > ago(90d)
| summarize percentile(CPUUsage, 95) by bin(Timestamp, 1d)
| render timechart
```

---

## Template Selection Guide

### Decision Tree

```
Start Here
├── Learning/POC?
│   └── Use: minimal_starter
│
├── Production ETL?
│   ├── Standard batch processing?
│   │   └── Use: basic_etl
│   ├── ML/AI workloads?
│   │   └── Use: advanced_analytics
│   └── Research/exploration?
│       └── Use: data_science
│
├── Real-Time Requirements?
│   ├── Streaming/IoT?
│   │   └── Use: realtime_streaming
│   └── Time-series/APM?
│       └── Use: specialized_timeseries
│
├── Enterprise Governance?
│   ├── Compliance-heavy (Healthcare/Finance)?
│   │   └── Use: compliance_regulated
│   └── Multi-domain organization?
│       └── Use: data_mesh_domain (per domain)
│
└── Migration Project?
    └── Use: migration_hybrid
```

### By Industry

| Industry | Recommended Template(s) |
|----------|-------------------------|
| Healthcare | compliance_regulated |
| Finance | compliance_regulated, specialized_timeseries |
| Manufacturing | realtime_streaming, specialized_timeseries |
| Retail | basic_etl, data_mesh_domain |
| Technology | advanced_analytics, realtime_streaming |
| Telecommunications | specialized_timeseries, realtime_streaming |
| Government | compliance_regulated |

### By Team Size

| Team Size | Recommended Template |
|-----------|---------------------|
| 1-2 people | minimal_starter, basic_etl |
| 3-10 people | basic_etl, advanced_analytics |
| 10-50 people | data_mesh_domain (per domain) |
| 50+ people | data_mesh_domain + compliance_regulated |

---

## Customization Guide

### 1. Clone and Modify

```bash
# Copy existing template
cp src/usf_fabric_cli/templates/blueprints/basic_etl.yaml src/usf_fabric_cli/templates/blueprints/my_custom_template.yaml

# Edit to your needs
vim src/usf_fabric_cli/templates/blueprints/my_custom_template.yaml

# Use custom template
python -m usf_fabric_cli.scripts.dev.generate_project "My Org" "My Project" \
  --template my_custom_template
```

### 2. Combine Templates

```yaml
# Take workspace config from basic_etl
workspace:
  name: "hybrid_project"
  # ... basic_etl settings

# Add real-time resources from realtime_streaming
resources:
  - type: "Eventstream"
    name: "my_stream"
  # ... more resources

# Add compliance principals from compliance_regulated
principals:
  - id: "${SECURITY_ADMIN_GROUP_OID}"
    role: "Admin"
  # ... more principals
```

### 3. Environment-Specific Customization

```yaml
# Base configuration (shared)
workspace:
  capacity_id: "${FABRIC_CAPACITY_ID}"

# Environment overrides
environments:
  dev:
    workspace:
      capacity_id: "F2"  # Trial for dev
      name: "project_dev"
  
  prod:
    workspace:
      capacity_id: "F64"  # Production capacity
      name: "project_prod"
```

---

## Support and Troubleshooting

### Common Issues

**Issue:** Template not found

```bash
# Solution: List available templates
ls -la src/usf_fabric_cli/templates/blueprints/

# Verify template name matches exactly
python -m usf_fabric_cli.scripts.dev.generate_project "Org" "Project" --template basic_etl
```

**Issue:** Principal permissions errors

```bash
# Solution: Use Object IDs (GUIDs), not email addresses
# Wrong: "user@company.com"
# Correct: "12345678-1234-1234-1234-123456789abc"

# Pro Tip: In v1.5.1+, you can pass a list of GUIDs in a single environment variable:
# In .env: MY_GROUP="guid1,guid2,guid3"
# In YAML: - id: "${MY_GROUP}"
```

**Issue:** Capacity not found

```bash
# Solution: Verify capacity ID exists and you have access
fabric-cicd diagnose --check-capacity "${FABRIC_CAPACITY_ID}"
```

### Getting Help

1. **Documentation:** See `docs/` folder for detailed guides
2. **Troubleshooting:** See [06_Troubleshooting.md](06_Troubleshooting.md)
3. **Examples:** See `config/projects/` for working examples
4. **Issues:** Open GitHub issue with template name and error details

---

## Version History

| Version | Date | Changes |
|---------|------|---------|
| 2.1.0 | 2026-02-10 | Added medallion template, renumbered catalog to 11 entries |
| 2.0.0 | 2025-12-10 | Added 6 new templates (realtime_streaming, minimal_starter, compliance_regulated, data_mesh_domain, migration_hybrid, specialized_timeseries) |
| 1.1.0 | 2025-11-28 | Updated basic_etl, advanced_analytics, data_science templates |
| 1.0.0 | 2025-11-15 | Initial release with 4 templates |

---

## Contributing

To contribute a new template:

1. Create YAML file in `src/usf_fabric_cli/templates/blueprints/`
2. Follow naming convention: `{category}_{purpose}.yaml`
3. Include comprehensive inline documentation
4. Add to `generate_project.py` choices list
5. Update this catalog document
6. Test end-to-end deployment
7. Submit pull request

**Template Quality Checklist:**

- ☐ All resources use `${VARIABLE}` placeholders
- ☐ Environment-specific overrides provided
- ☐ Principals use Object IDs (not emails)
- ☐ Inline documentation explains use cases
- ☐ Cost estimates included
- ☐ Minimum capacity specified
- ☐ Git integration optional (not required)
- ☐ Tested successfully in dev environment
