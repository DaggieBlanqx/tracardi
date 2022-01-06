from tracardi.service.storage.driver import storage
from tracardi_plugin_sdk.domain.register import Plugin, Spec, MetaData, FormGroup, FormField, FormComponent, Form, \
    Documentation, PortDoc
from tracardi_plugin_sdk.action_runner import ActionRunner
from tracardi_plugin_sdk.domain.result import Result
from tracardi_dot_notation.dot_accessor import DotAccessor
from tracardi.domain.resource import ResourceCredentials, Resource
from .model.maxmind_geolite2_client import GeoIpConfiguration, \
    PluginConfiguration, MaxMindGeoLite2, GeoLiteCredentials


def validate(config: dict) -> PluginConfiguration:
    return PluginConfiguration(**config)


class GeoIPAction(ActionRunner):

    @staticmethod
    async def build(**kwargs) -> 'GeoIPAction':
        config = validate(kwargs)
        resource = await storage.driver.resource.load(id=config.source.id)  # type: Resource
        return GeoIPAction(config, resource.credentials)

    def __init__(self, config: PluginConfiguration, credentials: ResourceCredentials):
        geoip2_config = GeoIpConfiguration(
            webservice=credentials.get_credentials(self, output=GeoLiteCredentials)
        )
        self.client = MaxMindGeoLite2(geoip2_config)
        self.config = config

    async def run(self, payload):
        try:
            dot = DotAccessor(self.profile, self.session, payload, self.event, self.flow)

            ip = dot[self.config.ip]

            location = await self.client.fetch(ip)

            result = {
                "city": location.city.name,
                "country": {
                    "name": location.country.name,
                    "code": location.country.iso_code
                },
                "county": location.subdivisions.most_specific.name,
                "postal": location.postal.code,
                "latitude": location.location.latitude,
                "longitude": location.location.longitude
            }
            return Result(port="location", value=result)
        except Exception as e:
            self.console.error(str(e))
            return Result(port="error", value={"payload": payload, "error": str(e)})


def register() -> Plugin:
    return Plugin(
        start=False,
        spec=Spec(
            module=__name__,
            className="GeoIPAction",
            inputs=["payload"],
            outputs=["location", "error"],
            version='0.6.1',
            license="MIT",
            author="Risto Kowaczewski",
            manual="geo_ip_locator",
            init={
                "source": {
                    "id": None,
                    "name": None,
                },
                "ip": "event@metadata.ip"
            },
            form=Form(groups=[
                FormGroup(
                    fields=[
                        FormField(
                            id="source",
                            name="Maxmind Geolite2 connection resource",
                            description="Select Maxmind Geolite2 server resource. Credentials from selected resource "
                                        "will be used to connect the service.",
                            required=True,
                            component=FormComponent(type="resource", props={"label": "resource", "tag": "geo-locator"})
                        )
                    ]
                ),
                FormGroup(
                    fields=[
                        FormField(
                            id="ip",
                            name="Path to ip",
                            description="Type path to IP data or IP address itself.",
                            component=FormComponent(type="dotPath", props={"label": "IP address"})
                        )
                    ]
                ),
            ]),
        ),
        metadata=MetaData(
            name='GeoIp service',
            desc='This plugin converts IP to location information.',
            icon='location',
            group=["Location"],
            documentation=Documentation(
                inputs={
                    "payload": PortDoc(desc="This port takes payload object.")
                },
                outputs={
                    "location": PortDoc(desc="Returns location."),
                    "error": PortDoc(desc="This port gets triggered if an error occurs.")
                }
            )
        )
    )
