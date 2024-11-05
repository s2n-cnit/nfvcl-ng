import httpx

from nfvcl.models.blueprint_ng.Athonet.core import AthonetAccessToken


class AthonetAuth(httpx.Auth):
    requires_response_body = True

    def __init__(self, access_token, refresh_token, mgmt_ip=None):
        self.access_token = access_token
        self.refresh_token = refresh_token
        self.api_url_ue = f"https://{mgmt_ip}/core/api/1/auth/refresh_token"
        self.client = httpx.Client(verify=False)

    def auth_flow(self, request):
        """
        For every request automatically add access token to it, if it's outdated automatically refresh it
        Args:
            request: client request

        """
        request.headers["Authorization"] = self.access_token
        response = yield request

        if response.status_code == 401:
            refresh_response = yield self.build_refresh_request()
            self.update_tokens(refresh_response)

            request.headers["Authorization"] = self.access_token
            yield request

    def build_refresh_request(self):
        """

        Returns: new pairs access token and refresh token

        """
        return self.client.post(self.api_url_ue, data={'refresh_token': f'{self.refresh_token}'}, )

    def update_tokens(self, response):
        """
        Updates access token and refresh token
        Args:
            response: json model containing access token and refresh token

        """
        token = AthonetAccessToken.model_validate(response.json())
        self.access_token = f"Bearer {token.access_token}"
        self.refresh_token = token.refresh_token
