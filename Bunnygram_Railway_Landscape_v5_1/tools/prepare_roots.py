"""Package a small, trusted root CA bundle for MicroPython.

Sourced from certifi's Mozilla trust store, NOT from unverified network content.
Change this selection if the actual Railway certificate issuer requires it.
"""
import re
from pathlib import Path
import certifi
from cryptography import x509

ROOT = Path(__file__).resolve().parents[1]
NAMES = ('CN=ISRG Root X1,', 'CN=ISRG Root X2,', 'CN=GTS Root R1,',
         'CN=GTS Root R3,', 'CN=DigiCert Global Root G2,',
         'CN=Amazon Root CA 1,', 'CN=GlobalSign Root R46,')

def write_bundle():
    raw=Path(certifi.where()).read_bytes()
    certs=re.findall(rb'-----BEGIN CERTIFICATE-----.*?-----END CERTIFICATE-----',raw,re.S)
    matched=[]
    for pem in certs:
        name=x509.load_pem_x509_certificate(pem).subject.rfc4514_string()
        if any(name.startswith(n) for n in NAMES):matched.append(pem+b'\n')
    if len(matched)<5:raise RuntimeError('Could not find required trusted CAs in certifi store')
    target=ROOT/'device'/'trust_roots.pem'
    target.write_bytes(b''.join(matched))
    print('Written',target,'with',len(matched),'trusted root certificates')
    return target

if __name__=='__main__':write_bundle()
