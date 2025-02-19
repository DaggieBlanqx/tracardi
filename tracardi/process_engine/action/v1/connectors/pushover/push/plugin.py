import urllib.parse
import aiohttp

from tracardi.domain.resource import ResourceCredentials
from tracardi.service.storage.driver import storage
from tracardi.service.plugin.domain.register import Plugin, Spec, MetaData, Form, FormGroup, FormField, FormComponent
from tracardi.service.plugin.runner import ActionRunner
from tracardi.service.plugin.domain.result import Result
from tracardi.service.notation.dot_template import DotTemplate
from .model.pushover_config import PushOverConfiguration, PushOverAuth


def validate(config: dict) -> PushOverConfiguration:
    return PushOverConfiguration(**config)


class PushoverAction(ActionRunner):

    @staticmethod
    async def build(**kwargs) -> 'PushoverAction':
        config = validate(kwargs)
        source = await storage.driver.resource.load(config.source.id)
        return PushoverAction(config, source.credentials)

    def __init__(self, config: PushOverConfiguration, credentials: ResourceCredentials):
        self.pushover_config = config
        self.credentials = credentials.get_credentials(self, output=PushOverAuth)  # type: PushOverAuth

    async def run(self, payload: dict, in_edge=None) -> Result:
        async with aiohttp.ClientSession() as session:

            dot = self._get_dot_accessor(payload)
            template = DotTemplate()

            data = {
                "token": self.credentials.token,
                "user": self.credentials.user,
                "message": template.render(self.pushover_config.message, dot)
            }

            result = await session.post(url='https://api.pushover.net/1/messages.json',
                                        data=urllib.parse.urlencode(data),
                                        headers={"Content-type": "application/x-www-form-urlencoded"})

            return Result(port="payload", value={
                "status": result.status,
                "body": await result.json()
            })


def register() -> Plugin:
    return Plugin(
        start=False,
        spec=Spec(
            module=__name__,
            className='PushoverAction',
            inputs=["payload"],
            outputs=['payload'],
            version='0.6.1',
            license="MIT",
            author="Bartosz Dobrosielski, Risto Kowaczewski",
            manual="send_pushover_msg_action",
            init={
                "source": None,
                "message": ""
            },
            form=Form(groups=[
                FormGroup(
                    name="Pushover source",
                    fields=[
                        FormField(
                            id="source",
                            name="Pushover authentication",
                            description="Select pushover resource",
                            component=FormComponent(
                                type="resource",
                                props={"label": "resource", "tag": "pushover"}
                            )
                        )
                    ]
                ),
                FormGroup(
                    name="Pushover message",
                    fields=[
                        FormField(
                            id="message",
                            name="Message",
                            description="Type message. Message can be in form of message template.",
                            component=FormComponent(
                                type="textarea",
                                props={
                                    "label": "Message template"
                                })
                        )
                    ]

                ),
            ]),

        ),
        metadata=MetaData(
            name='Pushover push',
            desc='Connects to Pushover app and pushes message.',
            icon='pushover',
            group=["Messaging"],
            tags=['messaging']
        )
    )
