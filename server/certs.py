"""Certificado HTTPS local, de graça.

Cria uma autoridade (CA) própria uma única vez e, a cada início, um certificado
do servidor assinado por ela com todos os IPs atuais do notebook. O tablet só
precisa instalar a CA uma vez; se o IP mudar, o certificado novo continua válido.
"""
import datetime as dt
import ipaddress
import socket
from pathlib import Path

import psutil
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.x509.oid import NameOID

DIR = Path(__file__).resolve().parent.parent / "certs"


def local_ips():
    ips = {"127.0.0.1"}
    for addrs in psutil.net_if_addrs().values():
        for a in addrs:
            if a.family == socket.AF_INET and not a.address.startswith("169.254."):
                ips.add(a.address)
    return sorted(ips)


def lan_ips():
    """IPs da rede local primeiro (Wi-Fi de casa), depois VPNs tipo Tailscale."""
    ips = [ip for ip in local_ips() if ip != "127.0.0.1"]
    return sorted(ips, key=lambda ip: not ip.startswith(("192.168.", "10.", "172.")))


def _name(cn):
    return x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, cn),
                      x509.NameAttribute(NameOID.ORGANIZATION_NAME, "Mesa local")])


def _save_key(key, path):
    path.write_bytes(key.private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.PKCS8,
        serialization.NoEncryption()))


def _load_ca():
    ca_key_p, ca_crt_p = DIR / "ca.key", DIR / "ca.crt"
    if ca_key_p.exists() and ca_crt_p.exists():
        key = serialization.load_pem_private_key(ca_key_p.read_bytes(), None)
        return key, x509.load_pem_x509_certificate(ca_crt_p.read_bytes())
    key = ec.generate_private_key(ec.SECP256R1())
    now = dt.datetime.now(dt.timezone.utc)
    cert = (x509.CertificateBuilder()
            .subject_name(_name("Mesa local CA"))
            .issuer_name(_name("Mesa local CA"))
            .public_key(key.public_key())
            .serial_number(x509.random_serial_number())
            .not_valid_before(now - dt.timedelta(days=1))
            .not_valid_after(now + dt.timedelta(days=3650))
            .add_extension(x509.BasicConstraints(ca=True, path_length=0), critical=True)
            .add_extension(x509.KeyUsage(False, False, False, False, False, True, True, False, False), critical=True)
            .add_extension(x509.SubjectKeyIdentifier.from_public_key(key.public_key()), critical=False)
            .sign(key, hashes.SHA256()))
    _save_key(key, ca_key_p)
    ca_crt_p.write_bytes(cert.public_bytes(serialization.Encoding.PEM))
    # versão DER, que o Android instala sem reclamar
    (DIR / "ca.cer").write_bytes(cert.public_bytes(serialization.Encoding.DER))
    return key, cert


def ensure_certs():
    """Devolve (cert, key) do servidor, recriando se os IPs mudaram."""
    DIR.mkdir(exist_ok=True)
    ca_key, ca_cert = _load_ca()
    ips = local_ips()
    host = socket.gethostname()
    crt_p, key_p = DIR / "server.crt", DIR / "server.key"

    if crt_p.exists() and key_p.exists():
        cur = x509.load_pem_x509_certificate(crt_p.read_bytes())
        san = cur.extensions.get_extension_for_class(x509.SubjectAlternativeName).value
        have = {str(i) for i in san.get_values_for_type(x509.IPAddress)}
        fresh = cur.not_valid_after_utc - dt.datetime.now(dt.timezone.utc) > dt.timedelta(days=30)
        if set(ips) <= have and fresh:
            return str(crt_p), str(key_p)

    key = ec.generate_private_key(ec.SECP256R1())
    now = dt.datetime.now(dt.timezone.utc)
    san = [x509.DNSName("localhost"), x509.DNSName(host), x509.DNSName(f"{host}.local")]
    san += [x509.IPAddress(ipaddress.ip_address(i)) for i in ips]
    cert = (x509.CertificateBuilder()
            .subject_name(_name(host))
            .issuer_name(ca_cert.subject)
            .public_key(key.public_key())
            .serial_number(x509.random_serial_number())
            .not_valid_before(now - dt.timedelta(days=1))
            .not_valid_after(now + dt.timedelta(days=397))
            .add_extension(x509.SubjectAlternativeName(san), critical=False)
            .add_extension(x509.BasicConstraints(ca=False, path_length=None), critical=True)
            .add_extension(x509.ExtendedKeyUsage([x509.oid.ExtendedKeyUsageOID.SERVER_AUTH]), critical=False)
            .add_extension(x509.AuthorityKeyIdentifier.from_issuer_public_key(ca_key.public_key()), critical=False)
            .sign(ca_key, hashes.SHA256()))
    _save_key(key, key_p)
    crt_p.write_bytes(cert.public_bytes(serialization.Encoding.PEM))
    return str(crt_p), str(key_p)
