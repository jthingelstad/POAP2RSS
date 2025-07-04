# AWS Setup Instructions for POAP2RSS

This guide will walk you through setting up all the necessary AWS services to deploy the POAP2RSS Lambda function.

## Prerequisites

- AWS Account with appropriate permissions
- POAP API credentials (API Key, Client ID, Client Secret)
- Domain name `app.poap2rss.com` (or ability to configure DNS)

## Step 1: Create DynamoDB Table

1. **Navigate to DynamoDB Console**
   - Go to AWS Console → DynamoDB → Tables

2. **Create Table**
   - Click "Create table"
   - **Table name**: `poap2rss-cache`
   - **Partition key**: `cache_key` (String)
   - **Sort key**: Leave empty
   - **Table settings**: Use default settings or customize as needed

3. **Configure TTL (Time to Live)**
   - After table is created, go to the table details
   - Click on "Additional settings" tab
   - Scroll down to "Time to live (TTL)"
   - Click "Enable TTL"
   - **TTL attribute name**: `ttl`
   - Click "Enable TTL"

4. **Note the Table ARN**
   - Go to "General information" tab
   - Copy the "Amazon Resource Name (ARN)" - you'll need this for IAM permissions

## Step 2: Create IAM Role for Lambda

1. **Navigate to IAM Console**
   - Go to AWS Console → IAM → Roles

2. **Create Role**
   - Click "Create role"
   - **Trusted entity type**: AWS service
   - **Service**: Lambda
   - Click "Next"

3. **Attach Policies**
   - Search for and select: `AWSLambdaBasicExecutionRole`
   - Click "Next"

4. **Configure Role**
   - **Role name**: `POAP2RSS-Lambda-Role`
   - **Description**: Role for POAP2RSS Lambda function
   - Click "Create role"

5. **Add DynamoDB Permissions**
   - Click on the newly created role
   - Click "Add permissions" → "Create inline policy"
   - Click "JSON" tab and paste:

```json
{
    "Version": "2012-10-17",
    "Statement": [
        {
            "Effect": "Allow",
            "Action": [
                "dynamodb:GetItem",
                "dynamodb:PutItem",
                "dynamodb:Query",
                "dynamodb:Scan",
                "dynamodb:UpdateItem",
                "dynamodb:DeleteItem"
            ],
            "Resource": "arn:aws:dynamodb:YOUR_REGION:YOUR_ACCOUNT_ID:table/poap2rss-cache"
        }
    ]
}
```

   - Replace `YOUR_REGION` and `YOUR_ACCOUNT_ID` with your actual values
   - **Policy name**: `POAP2RSS-DynamoDB-Policy`
   - Click "Create policy"

## Step 3: Create Lambda Function

1. **Navigate to Lambda Console**
   - Go to AWS Console → Lambda → Functions

2. **Create Function**
   - Click "Create function"
   - **Function name**: `POAP2RSS`
   - **Runtime**: Python 3.11 (or latest available)
   - **Architecture**: x86_64
   - **Execution role**: Use an existing role → `POAP2RSS-Lambda-Role`
   - Click "Create function"

3. **Configure Function**
   - **Timeout**: Change from 3 seconds to 30 seconds
   - **Memory**: 512 MB (adjust based on needs)

4. **Add Environment Variables**
   - Go to "Configuration" tab → "Environment variables"
   - Click "Edit" and add:
     - `POAP_API_KEY`: Your POAP API key
     - `POAP_CLIENT_ID`: Your POAP Client ID
     - `POAP_CLIENT_SECRET`: Your POAP Client Secret
     - `DYNAMODB_TABLE`: `poap2rss-cache`

5. **Deploy Function Code**
   - Go back to "Code" tab
   - Copy the entire Lambda function code from the artifact
   - Click "Deploy"

6. **Add Required Layer (for requests library)**
   - Go to "Code" tab → "Layers"
   - Click "Add a layer"
   - **Layer source**: Specify an ARN
   - **Layer version ARN**: `arn:aws:lambda:YOUR_REGION:770693421928:layer:Klayers-p311-requests:1`
   - Replace `YOUR_REGION` with your region (e.g., `us-east-1`)
   - Click "Add"

   *Note: This is a public layer that includes the requests library. You can also create your own layer if preferred.*

## Step 4: Create API Gateway

1. **Navigate to API Gateway Console**
   - Go to AWS Console → API Gateway

2. **Create API**
   - Click "Create API"
   - Choose "REST API" (not private)
   - Click "Build"

3. **Configure API**
   - **API name**: `POAP2RSS-API`
   - **Description**: API for POAP2RSS service
   - **Endpoint Type**: Regional
   - Click "Create API"

4. **Create Resources and Methods**

   **For Event Endpoint:**
   - Click "Actions" → "Create Resource"
   - **Resource Name**: `event`
   - **Resource Path**: `/event`
   - Check "Enable API Gateway CORS"
   - Click "Create Resource"
   
   - Select the `/event` resource
   - Click "Actions" → "Create Resource"
   - **Resource Name**: `{id}`
   - **Resource Path**: `/{id}`
   - Check "Enable API Gateway CORS"
   - Click "Create Resource"
   
   - Select the `/{id}` resource under `/event`
   - Click "Actions" → "Create Method"
   - Select "GET" from dropdown
   - Click the checkmark
   
   **For Address Endpoint:**
   - Click on the root "/"
   - Click "Actions" → "Create Resource"
   - **Resource Name**: `address`
   - **Resource Path**: `/address`
   - Check "Enable API Gateway CORS"
   - Click "Create Resource"
   
   - Select the `/address` resource
   - Click "Actions" → "Create Resource"
   - **Resource Name**: `{address}`
   - **Resource Path**: `/{address}`
   - Check "Enable API Gateway CORS"
   - Click "Create Resource"
   
   - Select the `/{address}` resource under `/address`
   - Click "Actions" → "Create Method"
   - Select "GET" from dropdown
   - Click the checkmark

5. **Configure Method Integration**
   
   **For both GET methods:**
   - **Integration type**: Lambda Function
   - **Use Lambda Proxy integration**: Check this box
   - **Lambda Region**: Your region
   - **Lambda Function**: `POAP2RSS`
   - Click "Save"
   - Click "OK" to grant permission

6. **Deploy API**
   - Click "Actions" → "Deploy API"
   - **Deployment stage**: New Stage
   - **Stage name**: `prod`
   - Click "Deploy"

7. **Note the Invoke URL**
   - Copy the "Invoke URL" from the stage details
   - It will look like: `https://abc123.execute-api.region.amazonaws.com/prod`

## Step 5: Configure Custom Domain (Optional but Recommended)

1. **Request SSL Certificate (if you don't have one)**
   - Go to AWS Certificate Manager
   - Click "Request a certificate"
   - **Domain name**: `app.poap2rss.com`
   - **Validation method**: DNS validation
   - Follow the validation process

2. **Create Custom Domain**
   - Go back to API Gateway console
   - Click "Custom domain names"
   - Click "Create"
   - **Domain name**: `app.poap2rss.com`
   - **Certificate**: Select your SSL certificate
   - Click "Create"

3. **Configure API Mappings**
   - Click on your custom domain
   - Click "API mappings" tab
   - Click "Configure API mappings"
   - **API**: `POAP2RSS-API`
   - **Stage**: `prod`
   - **Path**: Leave empty
   - Click "Save"

4. **Update DNS**
   - Note the "Target domain name" from your custom domain
   - In your DNS provider, create a CNAME record:
     - **Name**: `app.poap2rss.com`
     - **Value**: The target domain name from API Gateway

## Step 6: Test the Setup

1. **Test Lambda Function**
   - Go to Lambda console → Your function
   - Click "Test"
   - Use this test event:

```json
{
    "path": "/event/12345",
    "httpMethod": "GET"
}
```

2. **Test API Gateway**
   - Use the API Gateway test feature or make HTTP requests to:
   - `https://app.poap2rss.com/event/12345`
   - `https://app.poap2rss.com/address/0x1234567890abcdef`

## Step 7: Monitor and Maintain

1. **CloudWatch Logs**
   - Go to CloudWatch → Log groups
   - Find `/aws/lambda/POAP2RSS` log group
   - Monitor for errors and performance

2. **DynamoDB Monitoring**
   - Go to DynamoDB console → Your table
   - Check "Monitoring" tab for usage metrics

3. **API Gateway Monitoring**
   - Go to API Gateway → Your API → Dashboard
   - Monitor request count, latency, and errors

## Troubleshooting

**Common Issues:**

1. **Lambda timeout**: Increase timeout in Lambda configuration
2. **DynamoDB access denied**: Verify IAM role permissions
3. **API Gateway 502 errors**: Check Lambda function logs
4. **CORS issues**: Ensure CORS is enabled on API Gateway resources
5. **DNS propagation**: Custom domain may take time to propagate

**Useful Commands for Testing:**

```bash
# Test event feed
curl -H "Accept: application/rss+xml" https://app.poap2rss.com/event/12345

# Test address feed
curl -H "Accept: application/rss+xml" https://app.poap2rss.com/address/0x1234567890abcdef
```

## Security Considerations

1. **API Rate Limiting**: Consider adding rate limiting in API Gateway
2. **API Keys**: You can require API keys for additional security
3. **CORS**: Configure CORS appropriately for your use case
4. **Environment Variables**: Ensure sensitive data is properly secured

## Cost Optimization

1. **DynamoDB**: Use on-demand billing or provisioned capacity based on usage
2. **Lambda**: Monitor execution time and memory usage
3. **API Gateway**: Consider caching responses for frequently accessed endpoints

Your POAP2RSS service should now be fully operational at `https://app.poap2rss.com`!