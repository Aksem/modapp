from enum import Enum, unique
from typing import Dict

class InvalidArgumentError(Exception):
    def __init__(self, errors_by_fields: Dict[str, str]):
        self.errors_by_fields = errors_by_fields


class NotFoundError(Exception):
    ...


class ServerError(Exception):
    ...


@unique
class Status(Enum):
    """Predefined gRPC status codes represented as enum

    See also: https://github.com/grpc/grpc/blob/master/doc/statuscodes.md
    """
    #: The operation completed successfully
    OK = 0
    #: The operation was cancelled (typically by the caller)
    CANCELLED = 1
    #: Generic status to describe error when it can't be described using
    #: other statuses
    UNKNOWN = 2
    #: Client specified an invalid argument
    INVALID_ARGUMENT = 3
    #: Deadline expired before operation could complete
    DEADLINE_EXCEEDED = 4
    #: Some requested entity was not found
    NOT_FOUND = 5
    #: Some entity that we attempted to create already exists
    ALREADY_EXISTS = 6
    #: The caller does not have permission to execute the specified operation
    PERMISSION_DENIED = 7
    #: Some resource has been exhausted, perhaps a per-user quota, or perhaps
    #: the entire file system is out of space
    RESOURCE_EXHAUSTED = 8
    #: Operation was rejected because the system is not in a state required
    #: for the operation's execution
    FAILED_PRECONDITION = 9
    #: The operation was aborted
    ABORTED = 10
    #: Operation was attempted past the valid range
    OUT_OF_RANGE = 11
    #: Operation is not implemented or not supported/enabled in this service
    UNIMPLEMENTED = 12
    #: Internal errors
    INTERNAL = 13
    #: The service is currently unavailable
    UNAVAILABLE = 14
    #: Unrecoverable data loss or corruption
    DATA_LOSS = 15
    #: The request does not have valid authentication credentials for the
    #: operation
    UNAUTHENTICATED = 16
