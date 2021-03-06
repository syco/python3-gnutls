"""
GNUTLS constants
"""

__all__ = [
    # Credential types
    'CRED_CERTIFICATE', 'CRED_ANON',

    # X509 certificate/private key formats
    'X509_FMT_DER', 'X509_FMT_PEM',

    # Miscellaneous
    'CERT_REQUEST', 'CERT_REQUIRE', 'SHUT_RDWR', 'SHUT_WR'
]

__name_map__ = {
    'PROTO_TLS1_2': 'TLS1_2',
    'PROTO_TLS1_1': 'TLS1_1',
    'PROTO_TLS1_0': 'TLS1_0',
    'PROTO_SSL3': 'SSL3',
    'CRED_CERTIFICATE': 'CRD_CERTIFICATE',
    'CRED_ANON': 'CRD_ANON'
}

from gnutls.library import constants


class GNUTLSConstant(int):
    def __new__(cls, name):
        gnutls_name = 'GNUTLS_' + __name_map__.get(name, name)
        instance = int.__new__(cls, getattr(constants, gnutls_name))
        instance.name = name
        return instance

    def __repr__(self):
        return self.name


# Generate all exported constants
code = '\n'.join([f"{name} = GNUTLSConstant('{name}')" for name in __all__])
exec(code, locals(), globals())

del code
del constants
