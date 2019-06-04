import boto3
import botocore
import json 
# Set "running_locally" flag if you are running the integration test locally
running_locally = True

if running_locally:

    # Create Lambda SDK client to connect to appropriate Lambda endpoint
    lambda_client = boto3.client('lambda',
        region_name="us-east-2",
        endpoint_url="http://127.0.0.1:3001",
        use_ssl=False,
        verify=False,
        config=botocore.client.Config(
            signature_version=botocore.UNSIGNED,
            read_timeout=10,
            retries={'max_attempts': 1},
        )
    )
else:
    lambda_client = boto3.client('lambda')


# Invoke your Lambda function as you normally usually do. The function will run
# locally if it is configured to do so
response = json.loads(lambda_client.invoke(FunctionName="HelloWorldFunction")['Payload'].read())
body = json.loads(response["body"])

# Verify the response
assert body['message'] == "hello world"