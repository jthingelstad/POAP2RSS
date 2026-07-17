# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

POAP2RSS is an AWS Lambda-based service that generates RSS feeds for POAP (Proof of Attendance Protocol) events and collectors. The service converts POAP claim activity into standard RSS feeds that can be consumed by feed readers and automation tools.

## Architecture

- **Backend**: Single Python Lambda function (`src/poap2rss_lambda.py`) deployed on AWS. The repository and live `POAP2RSS` function in `us-east-1` target Python 3.14; production was verified on 2026-07-17.
- **Frontend**: Static HTML website in `www/` directory
- **Storage**: DynamoDB table for caching API responses (15-minute cache duration)
- **API Integration**: Authenticates with POAP API using OAuth2 client credentials flow
- **Deployment**: Lambda function with API Gateway, requires DynamoDB table named `poap2rss-cache`

## Key Implementation Details

### Lambda Function Structure
- Main handler: `lambda_handler(event, context)` in `src/poap2rss_lambda.py`
- Two feed types:
  - Event feeds: `/event/{event_id}` - Shows claims for a specific POAP event
  - Address feeds: `/address/{address}` - Shows POAPs collected by an address
- Returns RSS 2.0 XML format with proper content types

### POAP API Integration
- Base URL: `https://api.poap.tech`
- Authentication via OAuth2 with automatic token refresh
- Rate limiting and caching to minimize API calls
- Endpoints used:
  - `/event/{id}` - Get event details
  - `/actions/scan/{address}` - Get POAPs for an address
  - `/actions/claim-qr` - Get recent claims for an event

### Caching Strategy
- 15-minute cache in DynamoDB with TTL
- Cache key format: `event_{id}` or `address_{address}`
- Automatic cache invalidation via DynamoDB TTL attribute

### Environment Variables Required
- `DYNAMODB_TABLE`: Name of the DynamoDB cache table (default: `poap2rss-cache`)
- `POAP_API_KEY`: POAP API key
- `POAP_CLIENT_ID`: OAuth2 client ID
- `POAP_CLIENT_SECRET`: OAuth2 client secret
- `INACTIVITY_THRESHOLD_WEEKS`: Weeks before showing inactivity notice (default: 12)
- `TINYLYTICS_API_TOKEN`: Bearer token for Tinylytics hit tracking (optional)
- `TINYLYTICS_SITE_ID`: Numeric site ID for Tinylytics (optional)

## Development Commands

### Local development
```bash
uv sync --locked
uv run --locked ruff check .
uv run --locked ruff format --check .
uv run --locked python -m unittest discover -s tests
```

### Deployment
The Lambda is deployed manually with `scripts/deploy.sh lambda`. The script
exports the locked production dependencies, builds an x86_64-compatible zip,
uploads it to the existing `POAP2RSS` function, aligns the Lambda runtime with
`.python-version`, and removes obsolete layers.

Verify the deployed configuration without changing it:

```bash
aws lambda get-function-configuration \
  --region us-east-1 \
  --function-name POAP2RSS \
  --query '{Runtime:Runtime,Handler:Handler,Architectures:Architectures,State:State,LastUpdateStatus:LastUpdateStatus}'
```

API Gateway exposes `/event/{event_id}` and `/address/{address}` at
`https://app.poap2rss.com`.

## Code Conventions

- Single-file Lambda architecture for simplicity
- Type hints used throughout (`typing` module)
- Comprehensive error handling with fallback responses
- XML generation using `xml.etree.ElementTree`
- Logging via Python's standard `logging` module
- AWS SDK interactions via `boto3`
