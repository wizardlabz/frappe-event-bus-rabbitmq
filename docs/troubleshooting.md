# Troubleshooting

## How failures are classified

The provider maps every exception to `(message, retryable)`. That flag decides whether the core reschedules with backoff or dead-letters immediately.

| Condition | Message prefix | Retryable |
|---|---|---|
| Authentication rejected | `Authentication failed:` | **No** |
| Broker closed the channel | `Broker rejected the channel:` | **No** |
| Nacked or unroutable | `Message was not confirmed by the broker:` | **No** |
| Connection, timeout, DNS, socket | `Connection error:` | Yes |
| Anything unrecognised | `Unexpected error:` | Yes, and logged |

Authentication is checked first on purpose: `pika`'s `ProbableAuthenticationError` subclasses `AMQPConnectionError`, so checking connection errors first would misclassify bad credentials as retryable and burn the whole attempt budget on a password that will never work.

An unrecognised error defaults to retryable and writes an error-log entry titled *"RabbitMQ publish: unclassified error"*. If you see messages retrying with an `Unexpected error:` prefix, that log has the exception type.

---

## Connection refused / timeout

```
Connection error: [Errno 111] Connection refused
```

The broker is not reachable from the bench host.

- Confirm the broker is running: `docker ps`, or `systemctl status rabbitmq-server`.
- Check host and port on the connection — `5672` plain, `5671` TLS.
- From the bench host: `nc -zv <host> 5672`.
- In Docker, the bench and broker must share a network; `localhost` inside a container is not the host. Use the compose service name.

Retryable, so messages sit in `Retry Scheduled` and recover on their own once the broker returns.

## ACCESS_REFUSED

```
Authentication failed: ... ACCESS_REFUSED - Login was refused using authentication mechanism PLAIN
```

Credentials or vhost permissions are wrong. **Non-retryable** — the message is dead-lettered immediately.

- Verify username and password. Blank fields fall back to `guest`/`guest`.
- `guest` only works over loopback. Connecting from another host or container needs a real user.
- Check the user has permission on the vhost:

```bash
rabbitmqctl set_permissions -p / myuser ".*" ".*" ".*"
```

After fixing, **Replay** the dead-lettered messages.

## NOT_FOUND — no exchange

```
Broker rejected the channel: (404, "NOT_FOUND - no exchange 'foo' in vhost '/'")
```

Publishing to an exchange that does not exist. **Non-retryable.**

- Enable **Declare Exchange** on the destination, or
- Create the exchange on the broker.

Note the channel closes on this error, so the publish fails outright rather than silently dropping.

## PRECONDITION_FAILED

```
Broker rejected the channel: (406, "PRECONDITION_FAILED - inequivalent arg 'durable'...")
```

You are declaring an exchange or queue with parameters that differ from the existing one — commonly `durable` or the exchange type. **Non-retryable.**

Either match the existing configuration in the destination, or delete and recreate the broker object. Declaration is idempotent only when every parameter agrees.

## Message not confirmed

```
Message was not confirmed by the broker: ...
```

Only occurs with **Publisher Confirms** on. The broker either nacked the message or could not route it. **Non-retryable.**

An unroutable message usually means the routing key matches no binding — a `direct` exchange with a routing key nothing is bound to, or a `topic` pattern that does not match.

## Messages publish successfully but nothing arrives

The most common confusion, and not an error at all.

Without publisher confirms, `basic_publish` is fire-and-forget. Publishing to an exchange with no matching binding **succeeds** — the broker accepts the message and discards it.

- Check bindings in the management UI at <http://localhost:15672> under the exchange.
- Confirm the routing key matches the binding pattern.
- For `fanout`, confirm a queue is actually bound.
- Turn on **Publisher Confirms** to make unroutable messages fail loudly.

## Messages stuck in Pending

Not a provider problem — the core's worker has not run.

- Is the bus enabled in **Event Bus Settings**?
- Is the scheduler running? `bench --site <site> doctor`, then `bench --site <site> enable-scheduler`.

Publishing is enqueued after commit and retried by a job every 5 minutes; both need workers running.

## TLS errors

```
Connection error: [SSL: CERTIFICATE_VERIFY_FAILED] ...
```

- Set the port to `5671`. Enabling TLS does not change it for you.
- For a self-signed certificate in development, clear **TLS Verify** — but understand this disables certificate *and* hostname checking, leaving the connection encrypted but unauthenticated. Do not do this in production.

## Where to look

| Question | Where |
|---|---|
| What was published, and did it succeed? | **Event Bus Outbox Message** — status, `last_error`, attempt count |
| What happened on each attempt? | **Event Bus Delivery Attempt** — timings, error, provider response |
| Unclassified or unexpected errors | **Error Log** — search for `RabbitMQ publish` |
| Did the broker actually receive it? | RabbitMQ management UI, queue message counts |

Remember that `Failed` means the attempt budget ran out, while `Dead Lettered` means the provider judged a retry pointless. Both are replayable once you have fixed the cause.
