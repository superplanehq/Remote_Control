# Factory Remote settings. Put the values you don't want in git (the API
# token above all) in the badge's root secrets.py instead; any setting there
# overrides the default here.
#
#   SUPERPLANE_TOKEN      API token: SuperPlane > Profile > API token, or a
#                         service account token. Leave empty for demo mode.
#   SUPERPLANE_WORKSPACE  Workspace key, name or id (blank = first workspace)
#   SUPERPLANE_LINE       Factory line name (blank = the workspace's first line)
#   SUPERPLANE_URL        Only change this for a self-hosted SuperPlane
#   GITHUB_TOKEN          Optional. Lets the badge read changed files of
#                         private repositories.
SUPERPLANE_URL = "https://app.superplane.com"
SUPERPLANE_WORKSPACE = ""
SUPERPLANE_LINE = ""

# How often the board refreshes, in seconds. Each refresh is three requests.
REFRESH_SECONDS = 20
# How often an open task refreshes while its agent is working.
DETAIL_REFRESH_SECONDS = 8
