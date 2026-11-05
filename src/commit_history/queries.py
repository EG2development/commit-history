"""GraphQL documents used by the collector.

Every document selects ``rateLimit`` so the transport can account for the
points it spends and pause before the budget runs out.
"""

RATE_LIMIT = "rateLimit { cost remaining resetAt }"

OWNER = f"""
query Owner($login: String!) {{
  repositoryOwner(login: $login) {{
    __typename
    login
  }}
  {RATE_LIMIT}
}}
"""

REPOSITORIES = f"""
query Repositories($org: String!, $after: String) {{
  repositoryOwner(login: $org) {{
    repositories(first: 100, after: $after, ownerAffiliations: [OWNER],
                 orderBy: {{field: NAME, direction: ASC}}) {{
      pageInfo {{ hasNextPage endCursor }}
      nodes {{
        name
        nameWithOwner
        isArchived
        isFork
        isPrivate
        isEmpty
        pushedAt
        defaultBranchRef {{ name }}
      }}
    }}
  }}
  {RATE_LIMIT}
}}
"""

HISTORY = f"""
query History($owner: String!, $name: String!, $after: String, $since: GitTimestamp, $pageSize: Int!) {{
  repository(owner: $owner, name: $name) {{
    defaultBranchRef {{
      name
      target {{
        ... on Commit {{
          history(first: $pageSize, after: $after, since: $since) {{
            totalCount
            pageInfo {{ hasNextPage endCursor }}
            nodes {{
              oid
              committedDate
              authoredDate
              messageHeadline
              message
              additions
              deletions
              changedFilesIfAvailable
              parents {{ totalCount }}
              author {{ name email user {{ login }} }}
              committer {{ name email user {{ login }} }}
            }}
          }}
        }}
      }}
    }}
  }}
  {RATE_LIMIT}
}}
"""

TAGS = f"""
query Tags($owner: String!, $name: String!, $after: String) {{
  repository(owner: $owner, name: $name) {{
    refs(refPrefix: "refs/tags/", first: 100, after: $after) {{
      pageInfo {{ hasNextPage endCursor }}
      nodes {{
        name
        target {{
          oid
          ... on Tag {{ target {{ oid }} }}
        }}
      }}
    }}
  }}
  {RATE_LIMIT}
}}
"""

MEMBERS = f"""
query Members($org: String!, $after: String) {{
  organization(login: $org) {{
    membersWithRole(first: 100, after: $after) {{
      pageInfo {{ hasNextPage endCursor }}
      nodes {{ login }}
    }}
  }}
  {RATE_LIMIT}
}}
"""
