from config.settings import Neo4jConfig
from infrastructure.neo4j_client import Neo4jConnection


def test_connection_logs_failure_type_without_exception_details_or_password(caplog):
    password = "private-test-password"
    connection = Neo4jConnection(
        Neo4jConfig(
            uri="neo4j+s://example.databases.neo4j.io",
            user="test-user",
            password=password,
            database="neo4j",
        )
    )

    def fail_query(*args, **kwargs):
        raise RuntimeError(f"connection failed with {password}")

    connection.run_query = fail_query

    assert connection.test_connection() == (False, 0)
    assert "RuntimeError" in caplog.text
    assert "example.databases.neo4j.io" in caplog.text
    assert "connection failed" not in caplog.text
    assert password not in caplog.text
