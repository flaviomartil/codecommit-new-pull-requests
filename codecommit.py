import boto3
import requests
import json
import sqlite3
import time

def monitor_pull_requests(repo_name):
    session = boto3.Session(region_name='us-east-1')
    codecommit = session.client('codecommit')

    seen_pr_ids = set()

    while True:
        response = codecommit.list_pull_requests(
            repositoryName=repo_name,
            pullRequestStatus="OPEN",
        )
        
        auth_header = response['ResponseMetadata']['HTTPHeaders']['authorization']
        print(f"Authorization header: {auth_header}")

        for pr_id in response["pullRequestIds"]:
            if pr_id not in seen_pr_ids:
                seen_pr_ids.add(pr_id)
                pr_details = codecommit.get_pull_request(pullRequestId=pr_id)
                pr = pr_details["pullRequest"]
                repo_name = pr['targets'][0]['repositoryName']
                if repo_name not in ['SG3', 'SG3_API']:
                    continue
                print(f"New PR: {pr_id} - {pr['title']}")

        time.sleep(60)  # Aguarde 1 minuto antes de verificar novamente    


def create_database():
    conn = sqlite3.connect("repositories.db")
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS repositories
                (id text PRIMARY KEY, name text, description text, clone_url text)''')
    c.execute('''CREATE TABLE IF NOT EXISTS pull_requests
                (id text PRIMARY KEY, title text, source_branch,destination_branch,description text, author text, url text, repository_id text)''')
    conn.commit()
    conn.close()

def insert_repository(repo_id, repo_name, repo_description, repo_clone_url):
    conn = sqlite3.connect("repositories.db")
    c = conn.cursor()
    c.execute(f"INSERT OR REPLACE INTO repositories (id, name, description, clone_url) VALUES (?, ?, ?, ?)",
              (repo_id, repo_name, repo_description, repo_clone_url))
    conn.commit()
    conn.close()
   
def insert_pull_request(pull_request_id, title, description, source_branch, destination_branch, repository_id):
    conn = sqlite3.connect("repositories.db")
    c = conn.cursor()
    c.execute(f"INSERT OR REPLACE INTO pull_requests (id, title, description, source_branch, destination_branch, repository_id) VALUES (?, ?, ?, ?, ?, ?)",
              (pull_request_id, title, description, source_branch, destination_branch, repository_id))
    conn.commit()
    conn.close()

def get_repository_by_id(repo_id):
    conn = sqlite3.connect("repositories.db")
    c = conn.cursor()
    c.execute("SELECT * FROM repositories WHERE id=?", (repo_id,))
    result = c.fetchone()
    conn.close()

    return result

def get_repositories():
    codecommit = boto3.client("codecommit", region_name='us-east-1')

    repos = []
    next_token = None

    while True:
        if next_token:
            response = codecommit.list_repositories(nextToken=next_token)
        else:
            response = codecommit.list_repositories()

        repos.extend(response["repositories"])
        if "nextToken" in response:
            next_token = response["nextToken"]
        else:
            break

    return repos
def notify_webhook(types,title,pull_request_id,repo_name, repo_description,author,source_branch,destination_branch,repo_clone_url):
    # Defina a URL do webhook aqui
    webhook_url = "https://discord.com/api/webhooks/1098956439067824129/05zyY0-sD2I2PsYfOgYzSiKBVO2_7qUuAKJljbopfdg9i7tSASbOhgCH7ZAjYhniD1HY"


    data = {
        "embeds": [
            {
                "title": f"{types} {pull_request_id}",
                "url": repo_clone_url,
                "color": 16580705,
                "fields": [
                    {
                        "name": "Titulo",
                        "value": title,
                        "inline": True
                    },
                                          {
                        "name": "Descrição",
                        "value": repo_description,
                        "inline": False
                    },
                       {
                        "name": "",
                        "value": "",
                        "inline": False
                    },
                         {
                        "name": "Autor",
                        "value": author,
                        "inline": False
                    },
                    {
                        "name": "Branch origem",
                        "value": source_branch,
                        "inline": True
                    },
                        {
                        "name": "Branch destino",
                        "value": destination_branch,
                        "inline": True
                    },

                    {
                        "name": "URL de clone",
                        "value": repo_clone_url,
                        "inline": False
                    },
                ]
            }
        ]
    }

    headers = {
        "Content-Type": "application/json"
    }

    response = requests.post(webhook_url, data=json.dumps(data), headers=headers)

    if response.status_code == 204:
        print(repo_clone_url)
        print("Webhook notificado com sucesso.")
    else:
        print(f"Erro ao notificar webhook: {response.status_code}")

def get_pull_request_by_id(pull_request_id):
    conn = sqlite3.connect("repositories.db")
    c = conn.cursor()
    c.execute("SELECT * FROM pull_requests WHERE id=?", (pull_request_id,))
    result = c.fetchone()
    conn.close()

    return result        
        
def monitor_pull_requests(repository_name):
    codecommit = boto3.client("codecommit", region_name='us-east-1')
    
    while True:
        response = codecommit.list_pull_requests(repositoryName=repository_name, pullRequestStatus='OPEN')
        pull_request_ids = response.get('pullRequestIds', [])
        
        for pull_request_id in pull_request_ids:
            db_pull_request = get_pull_request_by_id(pull_request_id)

            if not db_pull_request:
                print(f"Nova pull request detectada no repositório {repository_name}: {pull_request_id}")
                pull_request = codecommit.get_pull_request(pullRequestId=pull_request_id)['pullRequest']
                commit_id = pull_request['pullRequestTargets'][0]['destinationCommit']
                title = pull_request['title']
                description = pull_request.get('description', '')
                author = pull_request['authorArn'].split('/')[-1]
                repository_id = pull_request['pullRequestTargets'][0]['repositoryName']
                source_branch = pull_request['pullRequestTargets'][0]['sourceReference'].split('/')[-1]
                destination_branch = pull_request['pullRequestTargets'][0]['destinationReference'].split('/')[-1]
                commit_metadata = codecommit.get_commit(repositoryName=repository_name, commitId=commit_id)
                url = f"https://us-east-1.console.aws.amazon.com/codesuite/codecommit/repositories/{repository_name}/pull-requests/{pull_request_id}/details?region=us-east-1"
                print(url)
                insert_pull_request(pull_request_id, title, description, author, url,destination_branch)
                notify_webhook('Nova pull request aberta',title,pull_request_id,repository_name, description,author,source_branch,destination_branch,url)

        time.sleep(60)  # Aguarde 1 minuto antes de verificar novamente     
def monitor_repositories():
    codecommit = boto3.client("codecommit", region_name='us-east-1')

    while True:
        current_repos = get_repositories()
        for repo in current_repos:
            repo_id = repo["repositoryId"]
            repo_name = repo["repositoryName"]
            repo_description = repo.get("repositoryDescription", "")
            repo_clone_url = repo.get("cloneUrlHttp", "")

            db_repo = get_repository_by_id(repo_id)

            if not db_repo:
                print(f"Novo repositório detectado: {repo_name}")
                insert_repository(repo_id, repo_name, repo_description, repo_clone_url)
                notify_webhook('Novo repositório',repo_name, repo_description, repo_clone_url)

        time.sleep(60)  # Aguarde 1 minuto antes de verificar novamente

if __name__ == "__main__":
    create_database()
    monitor_pull_requests('sg3')
    
