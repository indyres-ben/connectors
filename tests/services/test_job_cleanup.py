#
# Copyright Elasticsearch B.V. and/or licensed to Elasticsearch B.V. under one
# or more contributor license agreements. Licensed under the Elastic License 2.0;
# you may not use this file except in compliance with the Elastic License 2.0.
#

from unittest.mock import AsyncMock, Mock, patch

import pytest

from connectors.services.job_cleanup import IDLE_JOB_ERROR, JobCleanUpService
from tests.commons import AsyncIterator
from tests.services.test_base import create_and_run_service

CONFIG = {
    "elasticsearch": {
        "host": "http://nowhere.com:9200",
        "user": "elastic",
        "password": "changeme",
    },
    "service": {
        "max_errors": 20,
        "max_errors_span": 600,
        "job_cleanup_interval": 1,
    },
    "native_service_types": ["mongodb"],
}


def mock_connector(connector_id="1", index_name="index_name"):
    connector = Mock()
    connector.id = connector_id
    connector.index_name = index_name
    connector.sync_done = AsyncMock()
    return connector


def mock_sync_job(sync_job_id="1", connector_id="1", index_name="index_name"):
    job = Mock()
    job.job_id = sync_job_id
    job.connector_id = connector_id
    job.index_name = index_name
    job.fail = AsyncMock()
    job.reload = AsyncMock()
    return job


@pytest.mark.asyncio
@patch("connectors.protocol.SyncJobIndex.delete_jobs")
@patch("connectors.protocol.SyncJobIndex.idle_jobs")
@patch("connectors.protocol.SyncJobIndex.orphaned_jobs")
@patch("connectors.protocol.ConnectorIndex.fetch_by_id")
@patch("connectors.protocol.ConnectorIndex.supported_connectors")
@patch("connectors.protocol.ConnectorIndex.all_connectors")
async def test_cleanup_jobs(
    all_connectors,
    supported_connectors,
    connector_fetch_by_id,
    orphaned_jobs,
    idle_jobs,
    delete_jobs,
):
    existing_index_name = "foo"
    to_be_deleted_index_name = "bar"
    connector = mock_connector(index_name=existing_index_name)
    sync_job = mock_sync_job(index_name=to_be_deleted_index_name)
    another_sync_job = mock_sync_job(index_name=existing_index_name)

    all_connectors.return_value = AsyncIterator([connector])
    supported_connectors.return_value = AsyncIterator([connector])
    connector_fetch_by_id.return_value = connector
    orphaned_jobs.return_value = AsyncIterator([sync_job, another_sync_job])
    idle_jobs.return_value = AsyncIterator([sync_job])
    delete_jobs.return_value = {"deleted": 1, "failures": [], "total": 1}

    await create_and_run_service(JobCleanUpService, config=CONFIG, stop_after=0.1)

    delete_jobs.assert_called_with(job_ids=[sync_job.id, another_sync_job.id])
    sync_job.fail.assert_called_with(IDLE_JOB_ERROR)
    connector.sync_done.assert_called_with(job=sync_job)
