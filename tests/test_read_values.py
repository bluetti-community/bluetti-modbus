from unittest.mock import patch

import pytest
from modbus_connection.mock import MockModbusConnection

from bluetti_modbus_lib import Balco260, SMeter, read_values


@pytest.mark.asyncio
async def test_read_values_returns_the_decoded_values():
    conn = MockModbusConnection()
    conn.for_unit(1).holding[50001] = 2  # d_num_inverters

    values = await read_values(Balco260(conn.for_unit(1)))

    assert values["d_num_inverters"] == 2


@pytest.mark.asyncio
async def test_read_values_connects_on_demand_and_keeps_the_link():
    # A unit handed out by a shared connection is not connected beforehand;
    # the read opens it, and other devices leave it open for the next poll.
    conn = MockModbusConnection()

    await read_values(Balco260(conn.for_unit(1)))

    assert conn.connected is True


@pytest.mark.asyncio
async def test_read_values_on_an_smeter_drops_the_link_before_and_after():
    # An S Meter serves its measurements only on a connection's first read.
    conn = MockModbusConnection()
    await conn.connect()

    with patch.object(conn, "disconnect", wraps=conn.disconnect) as disconnect:
        await read_values(SMeter(conn.for_unit(1)))

    assert disconnect.await_count == 2
    assert conn.connected is False


@pytest.mark.asyncio
async def test_read_values_on_an_smeter_does_not_drop_a_link_it_never_had():
    conn = MockModbusConnection()

    with patch.object(conn, "disconnect", wraps=conn.disconnect) as disconnect:
        await read_values(SMeter(conn.for_unit(1)))

    assert disconnect.await_count == 1
