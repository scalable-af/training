from pygit2 import discover_repository, Repository, clone_repository, GIT_RESET_HARD
import boto3
import os
import stat
import shutil
import logging
import hmac
import hashlib
import json
import subprocess

# Setup our standard logger. We re-use the same format in most places so we have a standard presentation
logger = logging.getLogger()
logger.setLevel(logging.INFO)
logger.handlers[0].setFormatter(logging.Formatter('[%(asctime)s][%(levelname)s] %(message)s'))

# If true the function will delete all files at the end of each run
cleanup = False

# If true the function will hard reset the repo to head after each run
# This is needed because we are injecting comments directly into the markdown
# before compiling the site with Hugo. If we don't do this git will error
# with an error about locally changed files
reset = True

# The path that we will build hugo into for uploading to S3
build_path = "/tmp/hugo/public"

# In a real implementation this would be dynamic but we know we are only triggering
# on master. In a larger environment you might have different functions of logic
# depending on the branch that you were receiving a webhook for.
branch_name = "master"

# Initialized a repo, similar to running git init on the command line
def init_remote(repo, name, url):
    remote = repo.remotes.create(name, url, '+refs/*:refs/*')
    return remote

# Configured a remote/upstream association. The same as setting a remote on your repo via cli
def create_repo(repo_path, remote_url):
    if os.path.exists(repo_path):
        logger.info('Cleaning up repo path...')
        shutil.rmtree(repo_path)
    repo = clone_repository(remote_url, repo_path)

    return repo

# Pull the repo from the remote. Similar to doing a git clone, or git pull via the cli
def pull_repo(repo, branch_name, remote_url):
    remote_exists = False
    for r in repo.remotes:
        if r.url == remote_url:
            remote_exists = True
            remote = r
    if not remote_exists:
        remote = repo.create_remote('origin', remote_url)
    logger.info('Fetching and merging changes from %s branch %s', remote_url, branch_name)
    remote.fetch()
    if(branch_name.startswith('tags/')):
        ref = 'refs/' + branch_name
    else:
        ref = 'refs/remotes/origin/' + branch_name
    remote_branch_id = repo.lookup_reference(ref).target
    repo.checkout_tree(repo.get(remote_branch_id))
    repo.head.set_target(remote_branch_id)
    return repo

# This requires Python 3.5 or above, subprocess runs a command as if it were in the shell
# It also gives us the standard and error output for logging
def run_command(command):
    command_list = command.split(' ')
    try:
        logger.info("Running shell command: \"{0}\"".format(command))
        result = subprocess.run(command_list, stdout=subprocess.PIPE);
        logger.info("Command output:\n---\n{0}\n---".format(result.stdout.decode('UTF-8')))
    except Exception as e:
        logger.error("Exception: {0}".format(e))
        raise e
    return True


# Builds a hugo website using the source (the repo)
# and destination for the public content
def build_hugo(source_dir, destination_dir,debug=False):
    logger.info("Building Hugo site")
    run_command("/opt/hugo -s {0} -d {1}".format(source_dir,destination_dir))
    run_command("ls -l {0}".format(destination_dir))

# Uploads the built website to S3. We are using the AWS CLI because it has
# the sync feature which is a lot faster than doing a pure python implementation
# It might seem like an anti-pattern to shell out in a function when you could
# Do the same thing purely in code, but time is money on Lambda and this is
# significantly faster than doing a file at a time walking the directory
def upload_to_s3(local_path,s3_path):
    logger.info('Uploading Hugo site to S3: {0}'.format(s3_path))
    run_command('/opt/aws s3 rm s3://{0} --recursive'.format(s3_path))
    run_command('/opt/aws s3 sync {0} s3://{1}'.format(local_path,s3_path))
    run_command('/opt/aws s3 ls {0}'.format(s3_path))


# This is functional but likely isn't how you would really want to do this in production
# it will work perfectly well for our little site though and demonstrates how you can take
# Lambda and use it to glue things together in novel and highly functional ways.

# We are going to invoke the lambda function to read the comments based on the page name.
# We walk the hugo posts directory and find every .md file, strip the file type off and use 
# that as the key to look for comments with. On the Hugo side our template has a feature baked in
# where the comments form that is shown is injected with a hidden page value that matches the file name.
# That allows us to tie the two things together using a static site and back end functions
def add_comments(local_path, comment_function):
    lambda_client = boto3.client('lambda')
    # r=root, d=directories, f = files
    for r, d, f in os.walk(local_path):
        for file in f:
            # We only care about md files as those are posts we will inject into
            if '.md' in file:
                # We are setting this as a short circuit. We only want to look for
                # comments if the post has an appropriate comments section
                # this saves us lambda invokations for posts or files that don't have it
                show_comments = False
                file_name = file.split('.')[0]
                file_path = os.path.join(r, file)
                with open(file_path, 'r') as searchfile:
                        for line in searchfile:
                            if '### Comments' in line:
                                show_comments = True
                if show_comments:  
                    invoke_response = lambda_client.invoke(FunctionName=comment_function,
                                            Payload=json.dumps('{"page": "' + file_name + '"}'))
                    lambda_response = json.loads(invoke_response['Payload'].read())
                    comments = json.loads(lambda_response["body"])
                    logger.info(comments)
                    # Make sure we actually have some comments to write before trying to touch the file
                    if len(comments) > 0:
                        with open(file_path, 'a') as postfile:
                            # We inject the comments as simple unordered lists at the end of the file
                            # This is really brittle and requires writing our posts in a specific way
                            # but it works well for this lab
                            for comment in comments:
                                postfile.write('- {}\n'.format(comment["name"]))
                                postfile.write('  - {}\n'.format(comment["comment"]))


# This can be named whatever you want but a descriptive name is best if re-using functions
# A common pattern is to use the matching HTTP verb for a RESTful API
# We consume a webhook post, and a local invokation but we will just call this post.
def post(event, context):
    # Logging the entire event is a cheap simple way to make debugging easier
    # Often times just being able to see the event information quickly can help
    # Troubleshoot an issue faster than hooking up a debugger
    logger.info(event)

    # We always want to take the shortest path through our functions. Check for anything fatal first.
    try:
        output_bucket = os.environ['output_bucket']
    except:
        raise Exception('Output Bucket not defined. Set the environment variable for the function')
    
    try:
        comment_function = os.environ['comment_function']
    except:
        raise Exception('Comment Function not defined. Set the environment variable for the function')

    # Here we take a few steps to get the JSON into the body object
    # If this came in as a proxy request, or a direct API Gateway request
    # or a boto3 invokation the format of the body could be a few different types
    # With this stepped approach we can guarantee that no matter how this was called
    # we will have JSON in the body variable.
    if "body" in event:
        body = json.loads(event['body'])
    else:
        try:
            body = json.loads(event)
        except:
            body = event
 
    # We will still validate this before doing anything with it, but if we are missing
    # any essential components we should end early to save processing time.
    # No point in computing hashes for a payload that is missing data we need.
    try:
        full_name = body['repository']['full_name']
    except KeyError:
        raise Exception('Failed to find full_name in json post body')

    try:
        remote_url = body['repository']['clone_url']
    except KeyError:
        raise Exception('Failed to find clone_url name in json post body')

    # Another short circuit. If we know this wasn't called locally then it was likely
    # called via the webhook or some HTTP entity so we need to see what kind of event
    # it is and process it appropriately. Otherwise we can save ourself a bunch of validation
    if "local_invoke" not in body:
        
        try:
            github_secrets = os.environ['github_secrets']
        except:
            raise Exception('Github secrets not defined. Set the environment variable for the function')

        if "headers" in event and "X-GitHub-Event" in event['headers']:
            # We only care about push events, if this isn't one politely exit
            if event['headers']['X-GitHub-Event'] != "push":
                return {
                    "statusCode": 200,
                    "body": json.dumps('Skipping - Not a push event')
                }

        # We split this env variable because we could be re-using this function for multiple API
        # endpoints, multiple repos etc. It is best practice to have a secret per repo
        # so even if we use this exact endpoint we can still feed it multiple repos with multiple
        # keys. We define each key with a , to separate them.
        apikeys = github_secrets.split(',')

        # set a validation key, we will check multiple keys so it holds our result
        secure = False

        # Compute out the hash and validate the signature. If it passes set secure, otherwise throw an error
        if 'X-Hub-Signature' in event['headers'].keys():
            signature = event['headers']['X-Hub-Signature']
            for k in apikeys:
                computed_hash = hmac.new(k.encode('ascii'), event['body'].encode('ascii'), hashlib.sha1)
                computed_signature = '='.join(['sha1', computed_hash.hexdigest()])
                hmac.compare_digest(computed_signature.encode('ascii'), signature.encode('ascii'))
                if hmac.compare_digest(computed_signature.encode('ascii'), signature.encode('ascii')):
                    secure = True
        if secure == False:
            raise Exception('Failed to validate authenticity of webhook message')
    

    repo_name = full_name + '/branch/' + branch_name
    repo_path = '/tmp/%s' % repo_name

    # If we have an existing repo (if this function is still warm / is not a cold start)
    # we can re-use that repo on the file system and update it to save us some time and bandwidth
    try:
        repository_path = discover_repository(repo_path)
        repo = Repository(repository_path)
        logger.info('found existing repo, using that...')
    # If a previous repo is not found we will create it
    except Exception:
        logger.info('creating new repo for %s in %s' % (remote_url, repo_path))
        repo = create_repo(repo_path, remote_url)

    # Re-used or created, we now have a repo reference to pull against
    pull_repo(repo, branch_name, remote_url)

    # Now that we have the raw markdown files we can inject our comments
    # Into the markdown files before we compile the site so we take advantage
    # of all of the theme styling with minimal effort
    add_comments(repo_path + "/content/posts/", comment_function)

    # Compile the site to our pre-defined path
    build_hugo(repo_path, build_path)

    # Sync the site to our public s3 bucket for hosting
    upload_to_s3(build_path, output_bucket)

    if reset:
        logger.info('Resetting Repo...')
        repo.reset(repo.head.target, GIT_RESET_HARD)

    if cleanup:
        logger.info('Cleanup Lambda container...')
        shutil.rmtree(repo_path)

    # We have to return a status code otherwise the API Gateway will give a server error
    # however we are likely exceeding the 29s hard timeout limit on the API gateway
    # but if we can return correctly we should attempt to, that window could be changed later
    # or we could execute in time occasionally
    return {
            "statusCode": 200,
            "body": json.dumps('Successfully updated %s' % repo_name)
    }
