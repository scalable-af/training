# Lab 2.6 - Locally test our functions and configure VS code for live debugging

- Use Serverless to review logs of deployed functions and monitor deployments
- Use Invoke to run functions with custom payloads locally
- Use serverless-offline to emulate the API gateway for local testing

## Steps

1. To look at logs of functions we have to use the full name. Unfortunately that means we have to know the unique ID we gave to them. We can't select a generic name in a stack like we were able to do with SAM.
    - Tail the logs of our github_webhook and make a change to see it in action
        ```bash
        serverless logs -f Student00GithubWebhookSAM -t
        ```
2. Invoke a function locally, talking to external resources.
    - We can invoke local functions using  
    `sls invoke local -f FUNCTION_NAME`
    - Since we have to define our names in the `serverless.yml` we know what our table is named. Get your table name and unique ID from the serverless.yml or from the management console.
    - Now run
    ```bash
    echo '{"page": "first-post"}'|sam invoke local -f Student00CommentsGetSAM -e table_name=YOUR_TABLE_NAME 
    ```
    You should see something similar to 
    ```bash
        [2021-01-01 13:49:25,057][INFO] {'page': 'first-post'}

        [2021-01-01 13:49:25,081][INFO] Found credentials in shared credentials file: ~/.aws/credentials

        [2021-01-01 13:49:25,379][INFO] [{'comment': 'test2', 'uuid': 'dcd734e6-92cb-4797-9f44-ba2d4789a9e8', 'page': 'first-post', 'name': 'test'}]

        {
            "statusCode": "200",
            "body": "[{\"comment\": \"test2\", \"uuid\": \"dcd734e6-92cb-4797-9f44-ba2d4789a9e8\", \"page\": \"first-post\", \"name\": \"test\"}]",
            "headers": {
                "Content-Type": "application/json",
                "Access-Control-Allow-Origin": "*",
                "Access-Control-Allow-Headers": "Content-Type, X-Experience-API-Version,Authorization",
                "Access-Control-Allow-Methods": "POST, OPTIONS, GET, PUT"
            }
        }


    ```
    We have just locally invoked the same comment.get lambda handler that our github-webhook function uses to get comments for injection into the site. Our local function, using the table name connected to the remote DynamoDB using our credentials.

3. To test with the API Gateway we have to install serverless-offline
    - Use NPM to install serverless offline, from the serverless folder.
        ```bash
        npm install serverless-offline --save-dev
        ```
    - Add `- serverless-offline` to the plugins section of serverless.yml
    - You can start a local API Gateway with
        ```bash
        sls offline
        ```
    - Our functions need environment variables. Same as above we can pass them in with the -e flag
        ```bash
        sls offline -e table_name
        ```
    - You should see a message stating it is listening on localhost:3000 now.
    - Send a curl command to post a new comment 
        ```bash
        curl 'http://localhost:3000/comments' -H 'Content-Type: application/json' --data '{"name":"cli name","page":"first-post","comment":"cli comment"}'
        ```
    - You should see the logs in the window running the API server, and get a response from the comment function itself.
    - Note, that we called the function without a stage. This is a mocked API server, our real API endpoint in AWS includes the stage `Prod`. There are no stages in the mock API so you will have to adjust your requests based on that.
