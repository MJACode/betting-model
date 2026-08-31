"""
The SCRAM derivation in scripts/db_connect_probe.py, checked against RFC 7677.

This function is load-bearing for a diagnosis: it decides whether the password
in DATABASE_URL is the password Postgres holds. If it were subtly wrong it
would report NO MATCH for a correct credential and send someone off resetting
passwords that were never broken -- which is exactly the loop it was written to
end. So it is pinned to the published test vector rather than to itself.
"""

from scripts.db_connect_probe import scram_stored_key


def test_rfc7677_test_vector():
    # RFC 7677 section 3: password "pencil", salt W22ZaJ0SNY7soEsUEjb6gQ==,
    # 4096 iterations. StoredKey is the SHA-256 of the ClientKey.
    assert scram_stored_key("pencil", "W22ZaJ0SNY7soEsUEjb6gQ==", 4096) == \
        "WG5d8oPm3OtcPnkdi4Uo7BkeZkBFzpcXkuLmtbsT4qY="


def test_a_different_password_gives_a_different_key():
    salt = "W22ZaJ0SNY7soEsUEjb6gQ=="
    assert scram_stored_key("pencil", salt, 4096) != scram_stored_key("pencl", salt, 4096)


def test_a_different_salt_gives_a_different_key():
    assert scram_stored_key("pencil", "W22ZaJ0SNY7soEsUEjb6gQ==", 4096) != \
        scram_stored_key("pencil", "AAAAaJ0SNY7soEsUEjb6gQ==", 4096)


def test_iterations_matter():
    salt = "W22ZaJ0SNY7soEsUEjb6gQ=="
    assert scram_stored_key("pencil", salt, 4096) != scram_stored_key("pencil", salt, 8192)
