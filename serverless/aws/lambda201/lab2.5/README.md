# Lab 2.5 - Deploy our GitHub listener and static site pipeline with Serverless Framework

- Modify the template
- Deploy the template


## Steps

1. Modify the serverless.yml file
    - At the top of the file there is a section with everything we need to modify
    ```yaml
    custom:
        uniqueid: dfasasfg3a
        clone_url: https://github.com/scalable-af/training.git
        full_name: scalable-af/training
    ```
    - Put in some random numbers and letters for your uniqueid. Serverless doesn't create any unique IDs for it's objects, and it also has the ARN restrictions we discussed so you need to put this in manually.
2. Run the deployment
    - Run the deployment, everything should be prebuilt.
        -   If you get an error that it couldn't find python, you need to install python3.7 on your system.
    ```bash
    serverless deploy
    ```
    You should eventually get output similar to
    ```bash
    Service Information
    service: student00-static-blog-dfasasfg3a
    stage: dev
    region: us-east-1
    stack: student00-static-blog-dfasasfg3a-dev
    resources: 30
    api keys:
    None
    endpoints:
    POST - https://20ijbzdp18.execute-api.us-east-1.amazonaws.com/dev/webhook
    POST - https://20ijbzdp18.execute-api.us-east-1.amazonaws.com/dev/comments
    OPTIONS - https://20ijbzdp18.execute-api.us-east-1.amazonaws.com/dev/comments
    functions:
    Student00GithubWebhookSAM: github-webhook-dfasasfg3a
    Student00CommentsPostSAM: comment-post-dfasasfg3a
    Student00CommentsGetSAM: comment-get-dfasasfg3a
    Student00DynamoStreamSAM: dynamo-stream-dfasasfg3a
    layers:
    student00AwsCli: arn:aws:lambda:us-east-1:994185329081:layer:student00AwsCli:5
    student00Libc: arn:aws:lambda:us-east-1:994185329081:layer:student00Libc:5
    student00Hugo: arn:aws:lambda:us-east-1:994185329081:layer:student00Hugo:3

    ```
3. Update your github repo to use the new webhook path
4. Update your config.toml like previously to use the new comments endpoint
5. Unfortunately Serverless doesn't give us the option to specify output, so you will have to find the bucket name in the AWS UI based on the unique name you gave it.
6. Go to the site and add a comment to see it working end to end.
7. Now that you are familiar with multiple frameworks, take some time to try to modify this one. See if can restructure this into a single flat file. If it is packaged as a single zip, is it worth having a folder for a single file?

# Congratulations you have now deployed the same stake in three different ways. Manually by hand, with AWS SAM, and now Also with Serverless