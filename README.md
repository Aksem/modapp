# ModApp

**Goal of the ModApp** project is to find an optimal way of interprocess and interapplication language-agnostic communication and to provide reference implementation.

## Principles

TODO: detail explanations

- language-agnostic
- transport-agnostic
- encoding-agnostic
- contract-oriented (not required, but very recommended)
- don't force use ModApp on both ends, keep protocol open

## Existing solutions and comparison

- GRPC

- HTTP + WebSockets

- TRPC

## Status

The project is used in production by author, but it isn't ready for production usage by other developers because of:

- lack of tests
- lack of documentation

Existing solutions where ModApp is used to give a bit of understanding what technology already can:

- Python backend + Electron frontend (commercial)
- Python backend + Qt frontend (commercial)

Currently supported technologies:

- Python server:

  - Transports: grpc, web_socketify(http+websocket)
  - Converters: json, protobuf
  - Models: pydantic, dataclass

- JavaScript client: http+websocket and json/protobuf

## Python ModApp framework

- prefer code generation over magic and runtime overhead (at least in production version)
