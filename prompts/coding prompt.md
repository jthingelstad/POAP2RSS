I'm attaching a description for a service I would like to create called POAP2RSS. I would like you to write the Lambda function that would meet these requirements.

## Relevant information

- Please write this using Python and structure it for a Lambda function.
- Use the hostname app.poap2rss.com and then put the API (or RSS feeds) endpoints at /event and /address.
- It is okay to use Python packages such as Requests, or others to make the code more manageable and readable.
- Make sure to include relevant information for logging to Cloudwatch.
- Note the caching requirements included and the use of DynamoDB.
- The POAP API requires an API token. I have obtained a token from POAP and it can be provided via an environment variable.
- The POAP API requires an authentication token. I have the necessary Client ID and Client Secret and can be provided by an environment variable.

## Regarding authentication

Here is an example from POAP to retrieve an authentication token.

```
curl --location --request POST 
  --url 'https://auth.accounts.poap.xyz/oauth/token' 
  --header "Content-Type: application/json" 
  -data '{
  "audience": "https://api.poap.tech",
  "grant_type": "client_credentials",
  "client_id": "$clientid",
  "client_secret": "$clientsecret"   }'
```

