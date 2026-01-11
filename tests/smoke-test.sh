#!/bin/bash
# Production smoke tests for POAP2RSS
# Verifies that the API returns HTTP 200 and valid RSS XML

set -e

BASE_URL="https://app.poap2rss.com"
EVENT_ID="191490"
ADDRESS="poap.thingelstad.eth"

PASSED=0
FAILED=0

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
NC='\033[0m' # No Color

test_endpoint() {
    local name="$1"
    local url="$2"

    printf "Testing %-30s " "$name..."

    # Fetch with curl, capture HTTP status and body separately
    HTTP_STATUS=$(curl -s -o /tmp/response.xml -w "%{http_code}" "$url")

    # Check HTTP status
    if [ "$HTTP_STATUS" != "200" ]; then
        printf "${RED}FAIL${NC} (HTTP $HTTP_STATUS)\n"
        FAILED=$((FAILED + 1))
        return
    fi

    # Validate XML
    if xmllint --noout /tmp/response.xml 2>/dev/null; then
        printf "${GREEN}PASS${NC}\n"
        PASSED=$((PASSED + 1))
    else
        printf "${RED}FAIL${NC} (invalid XML)\n"
        FAILED=$((FAILED + 1))
    fi
}

echo "POAP2RSS Smoke Tests"
echo "===================="
echo ""

test_endpoint "Event feed" "$BASE_URL/event/$EVENT_ID"
test_endpoint "Address feed" "$BASE_URL/address/$ADDRESS"
test_endpoint "Event feed (nowarning)" "$BASE_URL/event/$EVENT_ID?nowarning=1"

echo ""
echo "===================="
echo "$PASSED passed, $FAILED failed"

# Clean up
rm -f /tmp/response.xml

# Exit with error if any tests failed
[ "$FAILED" -eq 0 ]
