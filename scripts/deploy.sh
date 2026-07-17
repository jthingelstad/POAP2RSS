#!/bin/bash
# Deployment script for POAP2RSS
# Usage: ./scripts/deploy.sh [lambda|website|all]

set -e

# Configuration
LAMBDA_FUNCTION_NAME="POAP2RSS"
S3_BUCKET="poap2rss.com"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
PYTHON_VERSION="$(tr -d '[:space:]' < "$PROJECT_DIR/.python-version")"
LAMBDA_RUNTIME="python${PYTHON_VERSION}"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
NC='\033[0m'

deploy_lambda() {
    echo -e "${YELLOW}Deploying Lambda function...${NC}"

    # Create temp directory
    TEMP_DIR=$(mktemp -d)
    PACKAGE_DIR="$TEMP_DIR/package"
    REQUIREMENTS_FILE="$TEMP_DIR/requirements.txt"
    mkdir -p "$PACKAGE_DIR"
    trap 'rm -rf "$TEMP_DIR"' EXIT

    echo "  Creating locked Python ${PYTHON_VERSION} x86_64 deployment package..."

    # Export the exact production dependency set and install Lambda-compatible wheels.
    uv export \
        --directory "$PROJECT_DIR" \
        --locked \
        --no-dev \
        --no-emit-project \
        --format requirements-txt \
        --output-file "$REQUIREMENTS_FILE"
    uv pip install \
        --target "$PACKAGE_DIR" \
        --requirements "$REQUIREMENTS_FILE" \
        --python-version "$PYTHON_VERSION" \
        --python-platform x86_64-manylinux2014 \
        --only-binary :all: \
        --no-compile

    # Lambda requires the handler module at the root of the deployment archive.
    cp "$PROJECT_DIR/src/poap2rss_lambda.py" "$PACKAGE_DIR/lambda_function.py"

    # Create zip file
    cd "$PACKAGE_DIR"
    zip -X -r9 "$PROJECT_DIR/lambda.zip" . --quiet
    cd "$PROJECT_DIR"

    echo "  Uploading locked code and dependencies..."

    # Deploy to Lambda
    aws lambda update-function-code \
        --function-name "$LAMBDA_FUNCTION_NAME" \
        --zip-file "fileb://$PROJECT_DIR/lambda.zip" \
        --output text --query 'FunctionArn'
    aws lambda wait function-updated --function-name "$LAMBDA_FUNCTION_NAME"

    echo "  Updating Lambda runtime to ${LAMBDA_RUNTIME} and removing obsolete layers..."

    aws lambda update-function-configuration \
        --cli-input-json "{\"FunctionName\":\"$LAMBDA_FUNCTION_NAME\",\"Runtime\":\"$LAMBDA_RUNTIME\",\"Layers\":[]}" \
        --output text --query 'Runtime'
    aws lambda wait function-updated --function-name "$LAMBDA_FUNCTION_NAME"

    aws lambda get-function-configuration \
        --function-name "$LAMBDA_FUNCTION_NAME" \
        --query '{Runtime:Runtime,Layers:Layers[*].Arn,State:State,LastUpdateStatus:LastUpdateStatus,LastModified:LastModified}'

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
