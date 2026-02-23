FROM ghcr.io/astral-sh/uv:python3.11-bookworm-slim

# Setup a non-root user
RUN groupadd --system --gid 999 tarxiv && \ 
    useradd --system --gid 999 --uid 999 --create-home tarxiv

# Enable bytecode compilation
ENV UV_COMPILE_BYTECODE=1
# Copy from the cache instead of linking since it's a mounted volume
ENV UV_LINK_MODE=copy
# Ensure installed tools can be executed out of the box
ENV UV_TOOL_BIN_DIR=/usr/local/bin

ARG API_PORT=9001
ENV TARXIV_API_PORT=${API_PORT}
EXPOSE ${TARXIV_API_PORT}

# Use tarxiv user to install and run our application
USER tarxiv
WORKDIR /app

# Install the project's dependencies using the lockfile and settings
RUN --mount=type=cache,target=/root/.cache/uv \
    --mount=type=bind,source=uv.lock,target=uv.lock \
    --mount=type=bind,source=pyproject.toml,target=pyproject.toml \
    uv sync --locked --no-install-project --no-dev

# Then, add the rest of the project source code and install it
# Installing separately from its dependencies allows optimal layer caching
COPY --chown=tarxiv:tarxiv . /app/ 
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --locked --no-dev

# Place executables in the environment at the front of the path
ENV PATH="/app/.venv/bin:$PATH"

ENTRYPOINT []
CMD ["/app/bin/start-api"]

