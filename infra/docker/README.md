# Docker Infrastructure

Stage 0 defines one image for the health service. Later bounded-context services should receive
their own Dockerfiles here while reusing the same explicitly pinned Python base version.
