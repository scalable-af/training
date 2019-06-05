# Lab 2.3 - Locally test our functions and configure VS code

- Use AWS SAM to review logs of deployed functions and monitor deployments.
- Use Invoke Local to run functions with custom payloads locally.
- Use the local API to emulate the API gateway for local testing.

Now that we have some functions and applications running in a CloudFormation stack via AWS SAM we likely want to be able to test them, and view logs locally without having to dig around the UI. Especially since CloudFormation gives all of the functions unique names for each stack. It can be a bit tricky tracking everything down. Fortunately AWS SAM has some built in features to make that all simpler.

## Steps

1. Invoke a function locally, talking to external resources.
    - We can invoke local functions using  
    `sam local invoke FUNCTION_NAME`
    - From the `source/sam` folder that has `template` in it, edit the `environment.json` file.
    - Go to CloudFormation, select your stack and look at the `Resources` list.
    - Find your DynamoDB Table name. It will be the only `AWS::DynamoDB::Table` type in the list, so you can search for it.
    - Replace the `table_name` in the `environment.json` file with your table name for both functions defined.
    - Now run
    ```bash
    echo '{"page": "first-post"}'|sam local invoke Student00CommentsGetSAM --env-vars environment.json 
    ```
    You should see something similar to 
    ```bash
    2021-01-01 08:38:16 Reading invoke payload from stdin (you can also pass it from file with --event)
    2021-01-01 08:38:16 Found credentials in shared credentials file: ~/.aws/credentials
    2021-01-01 08:38:16 Invoking comments.get (python3.7)

    Fetching lambci/lambda:python3.7 Docker container image......
    2021-01-01 08:38:16 Mounting /training/serverless/aws/lambda201/lab2.2/source/sam/comments as /var/task:ro,delegated inside runtime container
    START RequestId: 52fdfc07-2182-154f-163f-5f0f9a621d72 Version: $LATEST
    [2021-01-01 13:38:17,564][INFO] {'page': 'first-post'}
    [2021-01-01 13:38:17,588][INFO] Found credentials in environment variables.
    [2021-01-01 13:38:17,844][INFO] [{'comment': 'test comment', 'uuid': 'bad5dd9a-77e5-45dc-ad4b-18ebd02932c4', 'page': 'first-post', 'name': 'test name'}, {'comment': 'test comment', 'uuid': 'ce1a4da9-c999-484b-bdbf-b3c76e8b6fae', 'page': 'first-post', 'name': 'test name'}]

    ```
    We have just locally invoked the same comment.get lambda handler that our github-webhook function uses to get comments for injection into the site. Our local function, using the table name connected to the remote DynamoDB using our credentials.

2. Start a local API Gateway
    - You can start a local API Gatway with
        ```bash
        sam local start-api
        ```
    - Our functions need environment variables. You can use the environment variable same as above, or you can set the environment variable before running the gateway and all functions will picked it up. Replace your table name in the command below
        ```bash
        table_name="YOUr_TABLE_NAME" sam local start-api 
        ```
    - You should see a message stating it is listening on localhost:3000 now.
    - Send a curl command to post a new comment 
        ```bash
        curl 'http://localhost:3000/comments' -H 'Content-Type: application/json' --data '{"name":"cli name","page":"first-post","comment":"cli comment"}'
        ```
    - You should see the logs in the window running the API server, and get a response from the comment function itself.
    - Note, that we called the function without a stage. This is a mocked API server, our real API endipoint in AWS includes the stage `Prod`. There are no stages in the mock API so you will have to adjust your requests based on that.

3. We can also watch logs on remote functions while we interact with remote systems. Effectively tailing CloudWatch so we don't have to watch the webpage and refresh.
    - We can tail logs
        ```bash
        sam logs -n Student00GithubWebhookSAM --stack-name YOUR_STACK_NAME --tail
        ```
    - Now try posting a comment, and you should see the site being rebuilt based on the Dynamo trigger.
    - We can also get logs for a specific time window, if you know something happened during a certain time.
        ```bash
        sam logs -n Student00GithubWebhookSAM --stack-name YOUR_STACK_NAME -s '60min ago' -e '50min ago'
        ```
    - And we can filter the logs
        ```bash
        sam logs -n Student00GithubWebhookSAM --stack-name YOUR_STACK_NAME  --filter "error"
        ```
4. We can also run an invokation endpoint for running automated test.
    - Running `start-lambda` will run an API endpoint that lets you connect a boto3.client(lambda) to it.
    - Go into the `source/hello-world` and start the lambda server
        ```bash
        sam local start-lambda
        ```
    - Python run the integration test we have created
        ```bash
        python3 hello-world-test.py
        ```
    - If you get an error about boto3 not being installed you can pip3 install it.