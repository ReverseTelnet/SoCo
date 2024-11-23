"""Tests for the services module."""

# These tests require pytest.


import pytest

from soco.exceptions import SoCoUPnPException, UnknownSoCoException
from soco.services import Service, Action, Argument, Vartype

from unittest import mock

import xmltodict

# Dummy known-good errors/responses etc.  These are not necessarily valid as
# actual commands, but are valid XML/UPnP. They also contain unicode characters
# to test unicode handling.

DUMMY_ERROR = "".join(
    [
        '<?xml version="1.0"?>',
        "<s:Envelope ",
        'xmlns:s="http://schemas.xmlsoap.org/soap/envelope/" ',
        's:encodingStyle="http://schemas.xmlsoap.org/soap/encoding/">',
        "<s:Body>",
        "<s:Fault>",
        "<faultcode>s:Client</faultcode>",
        "<faultstring>UPnPError</faultstring>",
        "<detail>",
        '<UPnPError xmlns="urn:schemas-upnp-org:control-1-0">',
        "<errorCode>607</errorCode>",
        "<errorDescription>Oops μИⅠℂ☺ΔЄ💋</errorDescription>",
        "</UPnPError>",
        "</detail>",
        "</s:Fault>",
        "</s:Body>",
        "</s:Envelope>",
    ]
)  # noqa PEP8

DUMMY_ERROR_NO_ERROR_CODE = "".join(
    [
        '<?xml version="1.0"?>',
        "<s:Envelope ",
        'xmlns:s="http://schemas.xmlsoap.org/soap/envelope/" ',
        's:encodingStyle="http://schemas.xmlsoap.org/soap/encoding/">',
        "<s:Body>",
        "<s:Fault>",
        "<faultcode>s:Client</faultcode>",
        "<faultstring>UPnPError</faultstring>",
        "<detail>",
        '<UPnPError xmlns="urn:schemas-upnp-org:control-1-0">',
        "<errorDescription>Oops μИⅠℂ☺ΔЄ💋</errorDescription>",
        "</UPnPError>",
        "</detail>",
        "</s:Fault>",
        "</s:Body>",
        "</s:Envelope>",
    ]
)  # noqa PEP8

DUMMY_ERROR_EMPTY_RESPONSE = ""

DUMMY_VALID_RESPONSE = "".join(
    [
        '<?xml version="1.0"?>',
        '<s:Envelope xmlns:s="http://schemas.xmlsoap.org/soap/envelope/"',
        ' s:encodingStyle="http://schemas.xmlsoap.org/soap/encoding/">',
        "<s:Body>",
        "<u:GetLEDStateResponse ",
        'xmlns:u="urn:schemas-upnp-org:service:DeviceProperties:1">',
        "<CurrentLEDState>On</CurrentLEDState>",
        "<Unicode>μИⅠℂ☺ΔЄ💋</Unicode>",
        "</u:GetLEDStateResponse>",
        "</s:Body>",
        "</s:Envelope>",
    ]
)  # noqa PEP8

DUMMY_VALID_ACTION = "".join(
    [
        '<?xml version="1.0"?>',
        '<s:Envelope xmlns:s="http://schemas.xmlsoap.org/soap/envelope/"',
        ' s:encodingStyle="http://schemas.xmlsoap.org/soap/encoding/">',
        "<s:Body>",
        "<u:SetAVTransportURI ",
        'xmlns:u="urn:schemas-upnp-org:service:Service:1">',
        "<InstanceID>0</InstanceID>",
        "<CurrentURI>URI</CurrentURI>",
        "<CurrentURIMetaData></CurrentURIMetaData>",
        "<Unicode>μИⅠℂ☺ΔЄ💋</Unicode>" "</u:SetAVTransportURI>",
        "</s:Body>" "</s:Envelope>",
    ]
)  # noqa PEP8

DUMMY_VARTYPE = Vartype("string", None, None, None)

DUMMY_ACTIONS = [
    Action(
        name="Test",
        in_args=[
            Argument(name="Argument1", vartype=DUMMY_VARTYPE),
            Argument(name="Argument2", vartype=DUMMY_VARTYPE),
        ],
        out_args=[],
    )
]

DUMMY_ARGS = [("Argument1", 1), ("Argument2", 2)]

DUMMY_ARGS_ALTERNATIVE = [("Argument1", 3), ("Argument2", 2)]


@pytest.fixture()
def service():
    """A mock Service, for use as a test fixture."""

    mock_soco = mock.MagicMock()
    mock_soco.ip_address = "192.168.1.101"
    mock_service = Service(mock_soco)
    return mock_service


def test_init_defaults(service):
    """Check default properties are set up correctly."""
    assert service.service_type == "Service"
    assert service.version == 1
    assert service.service_id == "Service"
    assert service.base_url == "http://192.168.1.101:1400"
    assert service.control_url == "/Service/Control"
    assert service.scpd_url == "/xml/Service1.xml"
    assert service.event_subscription_url == "/Service/Event"


def test_method_dispatcher_function_creation(service):
    """Testing __getattr__ functionality."""
    import inspect

    # There should be no testing method
    assert "testing" not in service.__dict__.keys()
    # but we should be able to inspect it
    assert inspect.ismethod(service.testing)
    # and then, having examined it, the method should be cached on the instance
    assert "testing" in service.__dict__.keys()
    assert service.testing.__name__ == "testing"
    # check that send_command is actually called when we invoke a method
    service.send_command = lambda x, y: "Hello {}".format(x)
    assert service.testing(service) == "Hello testing"


def test_method_dispatcher_arg_count(service):
    """_dispatcher should pass its args to send_command."""
    service.send_command = mock.Mock()
    # http://bugs.python.org/issue7688
    # __name__ must be a string in python 2
    method = service.__getattr__("test")
    assert method("onearg")
    service.send_command.assert_called_with("test", "onearg")
    assert method()  # no args
    service.send_command.assert_called_with("test")
    assert method("one", cache_timeout=4)  # one arg + cache_timeout
    service.send_command.assert_called_with("test", "one", cache_timeout=4)


def test_wrap(service):
    """wrapping args in XML properly."""
    assert (
        service.wrap_arguments([("first", "one"), ("second", 2)])
        == "<first>one</first><second>2</second>"
    )
    assert service.wrap_arguments() == ""
    # Unicode
    assert (
        service.wrap_arguments([("unicode", "μИⅠℂ☺ΔЄ💋")])
        == "<unicode>μИⅠℂ☺ΔЄ💋</unicode>"
    )
    # XML escaping - do we also need &apos; ?
    assert (
        service.wrap_arguments([("weird", '&<"2')]) == "<weird>&amp;&lt;&quot;2</weird>"
    )


def test_unwrap(service):
    """unwrapping args from XML."""
    assert service.unwrap_arguments(DUMMY_VALID_RESPONSE) == {
        "CurrentLEDState": "On",
        "Unicode": "μИⅠℂ☺ΔЄ💋",
    }


def test_unwrap_invalid_char(service):
    """Test unwrapping args from XML with invalid char"""
    responce_with_invalid_char = DUMMY_VALID_RESPONSE.replace("μИⅠℂ☺ΔЄ💋", "AB")
    # Note, the invalid ^D (code point 0x04) should be filtered out
    assert service.unwrap_arguments(responce_with_invalid_char) == {
        "CurrentLEDState": "On",
        "Unicode": "AB",
    }


def test_compose(service):
    """Test argument composition."""
    service._actions = DUMMY_ACTIONS
    service.DEFAULT_ARGS = {}

    # Detect unknown action
    with pytest.raises(AttributeError):
        service.compose_args("Error", {})
    # Detect missing / unknown arguments
    with pytest.raises(ValueError):
        service.compose_args("Test", {"Argument1": 1})
    with pytest.raises(ValueError):
        service.compose_args("Test", dict(DUMMY_ARGS + [("Error", 3)]))

    # Check correct output
    assert service.compose_args("Test", dict(DUMMY_ARGS)) == DUMMY_ARGS

    # Set Argument1 = 1 as default
    service.DEFAULT_ARGS = dict(DUMMY_ARGS[:1])

    # Check that arguments are completed with default values
    assert service.compose_args("Test", dict(DUMMY_ARGS[1:])) == DUMMY_ARGS
    # Check that given arguments override the default values
    assert (
        service.compose_args("Test", dict(DUMMY_ARGS_ALTERNATIVE))
        == DUMMY_ARGS_ALTERNATIVE
    )


def test_build_command(service):
    """Test creation of SOAP body and headers from a command."""
    headers, body = service.build_command(
        "SetAVTransportURI",
        [
            ("InstanceID", 0),
            ("CurrentURI", "URI"),
            ("CurrentURIMetaData", ""),
            ("Unicode", "μИⅠℂ☺ΔЄ💋"),
        ],
    )
    assert body == DUMMY_VALID_ACTION
    assert headers == {
        "Content-Type": 'text/xml; charset="utf-8"',
        "SOAPACTION": "urn:schemas-upnp-org:service:Service:1#SetAVTransportURI",
    }


def test_build_custom_streaming_body():
    """Test Creation of Custom Streaming URL Meta Template"""
    meta_template = Service.build_custom_streaming_body(
        "CreateObject",
        "Deep Space One Title",
        "x-rincon-mp3radio://http://ice3.somafm.com/deepspaceone-128-mp3",
        "Whoa! Space is So Huge.",
    )

    # Simple Tests
    meta_dictionary = xmltodict.parse(meta_template)
    container_id = meta_dictionary["s:Envelope"]["s:Body"]["u:CreateObject"][
        "ContainerID"
    ]
    assert container_id == "FV:2"

    # Climbing Down the Tree of Nested XML
    elements = meta_dictionary["s:Envelope"]["s:Body"]["u:CreateObject"]["Elements"]
    elements_dictionary = xmltodict.parse(elements)

    # Mid-Level XML Test
    res_dictionary = elements_dictionary["DIDL-Lite"]["item"]["res"]
    assert (
        res_dictionary["#text"]
        == "x-rincon-mp3radio://http://ice3.somafm.com/deepspaceone-128-mp3"
    )

    # Deep XML Test
    resmd_results = elements_dictionary["DIDL-Lite"]["item"]["r:resMD"]
    resmd_dictionary = xmltodict.parse(resmd_results)
    resmd_items = resmd_dictionary["DIDL-Lite"]["item"]
    assert resmd_items["@id"] == "R:0/0/0"
    assert resmd_items["@parentID"] == "FV:2"
    assert resmd_items["dc:title"] == "Deep Space One Title"
    assert resmd_items["desc"]["#text"] == "SA_RINCON65031_"


def test_add_custom_streaming_url_as_favorite(service):
    """Test Adding a Custom Streaing URL as a Favorite"""
    response = mock.MagicMock()
    response.encoding = "utf-8"
    response.headers = {
        "CONTENT-LENGTH": "2049",
        "CONTENT-TYPE": 'text/xml; charset="utf-8"',
        "Connection": "close",
    }
    response.text = '<s:Envelope xmlns:s="http://schemas.xmlsoap.org/soap/envelope/" s:encodingStyle="http://schemas.xmlsoap.org/soap/encoding/"><s:Body><u:CreateObjectResponse xmlns:u="urn:schemas-upnp-org:service:ContentDirectory:1"><ObjectID>FV:2/161</ObjectID><Result>&lt;DIDL-Lite xmlns:dc=&quot;http://purl.org/dc/elements/1.1/&quot; xmlns:upnp=&quot;urn:schemas-upnp-org:metadata-1-0/upnp/&quot; xmlns:r=&quot;urn:schemas-rinconnetworks-com:metadata-1-0/&quot; xmlns=&quot;urn:schemas-upnp-org:metadata-1-0/DIDL-Lite/&quot;&gt;&lt;item id=&quot;FV:2/161&quot; parentID=&quot;FV:2&quot; restricted=&quot;false&quot;&gt;&lt;dc:title&gt;Deep Space One Title&lt;/dc:title&gt;&lt;upnp:class&gt;object.itemobject.item.sonos-favorite&lt;/upnp:class&gt;&lt;r:ordinal&gt;3&lt;/r:ordinal&gt;&lt;res protocolInfo=&quot;x-rincon-mp3radio:*:audio/x-rincon-mp3radio:*&quot;&gt;x-rincon-mp3radio://http://ice3.somafm.com/deepspaceone-128-mp3&lt;/res&gt;&lt;r:type&gt;instantPlay&lt;/r:type&gt;&lt;r:description&gt;Whoa! Space is So Huge.&lt;/r:description&gt;&lt;r:resMD&gt;&amp;lt;DIDL-Lite\n                        xmlns:dc=&amp;quot;http://purl.org/dc/elements/1.1/&amp;quot;\n                        xmlns:upnp=&amp;quot;urn:schemas-upnp-org:metadata-1-0/upnp/&amp;quot;\n                        xmlns:r=&amp;quot;urn:schemas-rinconnetworks-com:metadata-1-0/&amp;quot;\n                        xmlns=&amp;quot;urn:schemas-upnp-org:metadata-1-0/DIDL-Lite/&amp;quot;&amp;gt;&amp;lt;item id=&amp;quot;R:0/0/0&amp;quot; parentID=&amp;quot;FV:2&amp;quot; restricted=&amp;quot;true&amp;quot;&amp;gt;&amp;lt;dc:title&amp;gt;Deep Space One Title&amp;lt;/dc:title&amp;gt;&amp;lt;upnp:class&amp;gt;object.item.audioItem.audioBroadcast&amp;lt;/upnp:class&amp;gt;&amp;lt;desc id=&amp;quot;cdudn&amp;quot; nameSpace=&amp;quot;urn:schemas-rinconnetworks-com:metadata-1-0/&amp;quot;&amp;gt;SA_RINCON65031_&amp;lt;/desc&amp;gt;&amp;lt;/item&amp;gt;&amp;lt;/DIDL-Lite&amp;gt;&lt;/r:resMD&gt;&lt;/item&gt;&lt;/DIDL-Lite&gt;</Result></u:CreateObjectResponse></s:Body></s:Envelope>'
    with mock.patch("requests.post", return_value=response) as fake_post:
        result = service.add_custom_streaming_url_as_favorite(
            "CreateObject",
            "Deep Space One Title",
            "x-rincon-mp3radio://http://ice3.somafm.com/deepspaceone-128-mp3",
            "Whoa! Space is So Huge.",
        )

        # Simple Tests
        assert result.headers["CONTENT-LENGTH"] == "2049"
        assert result.encoding == "utf-8"

        # Mid-Level XML Test
        meta_dictionary = xmltodict.parse(result.text)
        create_object_results = meta_dictionary["s:Envelope"]["s:Body"][
            "u:CreateObjectResponse"
        ]["Result"]
        create_object_dictionary = xmltodict.parse(create_object_results)
        res_dictionary = create_object_dictionary["DIDL-Lite"]["item"]["res"]
        assert (
            res_dictionary["#text"]
            == "x-rincon-mp3radio://http://ice3.somafm.com/deepspaceone-128-mp3"
        )

        # Deep XML Test
        resmd_results = create_object_dictionary["DIDL-Lite"]["item"]["r:resMD"]
        resmd_dictionary = xmltodict.parse(resmd_results)
        resmd_items = resmd_dictionary["DIDL-Lite"]["item"]
        assert resmd_items["@id"] == "R:0/0/0"
        assert resmd_items["@parentID"] == "FV:2"
        assert resmd_items["dc:title"] == "Deep Space One Title"
        assert resmd_items["desc"]["#text"] == "SA_RINCON65031_"


def test_send_command(service):
    """Calling a command should result in a http request, unless the cache is
    hit."""
    response = mock.MagicMock()
    response.headers = {}
    response.status_code = 200
    response.text = DUMMY_VALID_RESPONSE
    with mock.patch("requests.post", return_value=response) as fake_post:
        result = service.send_command(
            "SetAVTransportURI",
            [
                ("InstanceID", 0),
                ("CurrentURI", "URI"),
                ("CurrentURIMetaData", ""),
                ("Unicode", "μИⅠℂ☺ΔЄ💋"),
            ],
            cache_timeout=2,
        )
        assert result == {"CurrentLEDState": "On", "Unicode": "μИⅠℂ☺ΔЄ💋"}
        fake_post.assert_called_once_with(
            "http://192.168.1.101:1400/Service/Control",
            headers=mock.ANY,
            data=DUMMY_VALID_ACTION.encode("utf-8"),
            timeout=20,
        )
        # Now the cache should be primed, so try it again
        fake_post.reset_mock()
        result = service.send_command(
            "SetAVTransportURI",
            [
                ("InstanceID", 0),
                ("CurrentURI", "URI"),
                ("CurrentURIMetaData", ""),
                ("Unicode", "μИⅠℂ☺ΔЄ💋"),
            ],
            cache_timeout=0,
        )
        # The cache should be hit, so there should be no http request
        assert not fake_post.called
        # but this should not affefct a call with different params
        fake_post.reset_mock()
        result = service.send_command(
            "SetAVTransportURI",
            [
                ("InstanceID", 1),
                ("CurrentURI", "URI2"),
                ("CurrentURIMetaData", "abcd"),
                ("Unicode", "μИⅠℂ☺ΔЄ💋"),
            ],
        )
        assert fake_post.called
        # calling again after the time interval will avoid the cache
        fake_post.reset_mock()
        import time

        time.sleep(2)
        result = service.send_command(
            "SetAVTransportURI",
            [
                ("InstanceID", 0),
                ("CurrentURI", "URI"),
                ("CurrentURIMetaData", ""),
                ("Unicode", "μИⅠℂ☺ΔЄ💋"),
            ],
        )
        assert fake_post.called


def test_handle_upnp_error(service):
    """Check errors are extracted properly."""
    with pytest.raises(SoCoUPnPException) as E:
        service.handle_upnp_error(DUMMY_ERROR)
    assert (
        "UPnP Error 607 received: Signature Failure from 192.168.1.101"
        == E.value.message
    )
    assert E.value.error_code == "607"
    assert E.value.error_description == "Signature Failure"


def test_handle_upnp_error_with_no_error_code(service):
    """Check errors are extracted properly."""
    with pytest.raises(UnknownSoCoException):
        service.handle_upnp_error(DUMMY_ERROR_NO_ERROR_CODE)


def test_handle_upnp_error_with_empty_response(service):
    """Check errors are extracted properly."""
    with pytest.raises(UnknownSoCoException):
        service.handle_upnp_error(DUMMY_ERROR_EMPTY_RESPONSE)


# TODO: test iter_actions
