#!/bin/bash
# Deployment script for POAP2RSS
# Usage: ./scripts/deploy.sh [lambda|website|all]

set -e

# Configuration
LAMBDA_FUNCTION_NAME="POAP2RSS"
S3_BUCKET="poap2rss.com"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
NC='\033[0m'

deploy_lambda() {
    echo -e "${YELLOW}Deploying Lambda function...${NC}"

    # Create temp directory
    TEMP_DIR=$(mktemp -d)
    trap "rm -rf $TEMP_DIR" EXIT

    echo "  Creating deployment package..."

    # Install dependencies
    pip install --target "$TEMP_DIR" requests --quiet

    # Copy Lambda function (boto3 is provided by AWS Lambda runtime)
    cp "$PROJECT_DIR/src/poap2rss_lambda.py" "$TEMP_DIR/lambda_function.py"

    # Create zip file
    cd "$TEMP_DIR"
    zip -r9 "$PROJECT_DIR/lambda.zip" . --quiet
    cd "$PROJECT_DIR"

    echo "  Uploading to AWS Lambda..."

    # Deploy to Lambda
    aws lambda update-function-code \
        --function-name "$LAMBDA_FUNCTION_NAME" \
        --zip-file "fileb://$PROJECT_DIR/lambda.zip" \
        --output text --query 'FunctionArn'

    # Clean up zip file
    rm -f "$PROJECT_DIR/lambda.zip"

    echo -e "${GREEN}Lambda deployment complete!${NC}"
}

deploy_website() {
    echo -e "${YELLOW}Deploying website to S3...${NC}"

    # Sync www directory to S3
    aws s3 sync "$PROJECT_DIR/www/" "s3://$S3_BUCKET/" \
        --delete \
        --cache-control "max-age=3600"

    echo -e "${GREEN}Website deployment complete!${NC}"
}

# Parse command line argument
COMMAND="${1:-all}"

case "$COMMAND" in
    lambda)
        deploy_lambda
        ;;
    website)
        deploy_website
        ;;
    all)
        deploy_lambda
        deploy_website
        ;;
    *)
        echo "Usage: $0 [lambda|website|all]"
        echo "  lambda  - Deploy Lambda function only"
        echo "  website - Deploy static website to S3 only"
        echo "  all     - Deploy both (default)"
        exit 1
        ;;
esac

echo -e "${GREEN}Deployment finished!${NC}"
