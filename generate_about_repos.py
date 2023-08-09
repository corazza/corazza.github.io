import os

import requests

GITHUB_GRAPHQL_ENDPOINT = "https://api.github.com/graphql"


def get_pinned_repositories(username, token):
    query = f"""
    {{
      user(login: "{username}") {{
        pinnedItems(first: 10) {{
          nodes {{
            ... on Repository {{
              name
              url
              description
              stargazers {{
                totalCount
              }}
              primaryLanguage {{
                name
              }}
            }}
          }}
        }}
      }}
    }}
    """

    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }

    response = requests.post(GITHUB_GRAPHQL_ENDPOINT, json={
                             'query': query}, headers=headers)

    if response.status_code == 200:
        return response.json()['data']['user']['pinnedItems']['nodes']
    else:
        print(f"Error {response.status_code}: {response.text}")
        return []


def generate_markdown(repositories):
    output = '## My projects\n\n'
    for repo in repositories:
        repo_name = repo['name']
        repo_url = repo['url']
        repo_desc = repo['description'] if repo['description'] else 'No description provided.'
        repo_language = repo['primaryLanguage']['name'] if repo.get(
            'primaryLanguage') else 'Unknown'
        stars = repo['stargazers']['totalCount']

        output += f"- **[{repo_name}]({repo_url})**  \n  {repo_desc}  \n  _Language: {repo_language} | ⭐ {stars}_\n\n"

    return output


def main():
    username = 'corazza'
    token = os.environ.get('GITHUB_API_TOKEN')

    if not token:
        print("Please set the GITHUB_API_TOKEN environment variable.")
        return

    repositories = get_pinned_repositories(username, token)
    markdown_output = generate_markdown(repositories)

    print(markdown_output)

    with open('pinned_repos.md', 'w') as f:
        f.write(markdown_output)


if __name__ == '__main__':
    main()
