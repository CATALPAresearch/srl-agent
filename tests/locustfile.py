from locust import HttpUser, task, between


class InterviewAgentUser(HttpUser):
    wait_time = between(1, 3)

    def on_start(self):
        # The server issues the identity; requests carry it as a bearer token.
        token = self.client.post("/session/identity").json()["token"]
        self.client.headers["Authorization"] = f"Bearer {token}"
        self.client.post("/startConversation", json={"client": "web", "language": "en"})

    @task
    def reply(self):
        self.client.post("/reply", json={
            "client": "web",
            "message": "Hello, how are you?"
        })
