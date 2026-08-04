# syntax=docker/dockerfile:1

# --- packingsolver-builder: build the pinned PackingSolver executable --------
# cutting-engine's PackingSolver provider (docs/PACKINGSOLVER_PROVIDER_SPEC.md,
# "Packing and deployment") is a local subprocess Mebel Pro's image must
# install; the Python wheel stays platform-independent. Upstream is MIT
# licensed (fontanf/packingsolver); source is never vendored into this repo,
# only fetched, checksummed, and built here.
FROM python:3.12-slim AS packingsolver-builder

# Provided by BuildKit; drives the arm64-only CoinOR workaround below.
ARG TARGETARCH

# Pin the exact upstream commit and archive checksum — never `latest`, never
# an unpinned revision (PACKINGSOLVER_PROVIDER_SPEC.md, "Fixed decisions").
ARG PACKINGSOLVER_COMMIT=6915ff627a70ee0d71f5adca81f0ecbb0d0579e4
ARG PACKINGSOLVER_SHA256=d3b60f82ff05206a8fa75fbf55e6e12bbe225ec29d45133600300344a739b7cb

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
         build-essential git curl ca-certificates liblapack-dev libbz2-dev zlib1g-dev \
    && rm -rf /var/lib/apt/lists/*

# --- arm64: supply CoinOR CLP ourselves --------------------------------------
# On Linux, packingsolver → mathoptsolverscmake FetchContents *prebuilt x86_64*
# CoinUtils/Clp release archives; upstream publishes no arm64 Linux build, so an
# arm64 host links x86_64 objects and dies with
#   libClp.a: error adding symbols: file in wrong format  (Relocations in generic ELF, EM: 62)
# Dropping CLP is not an option: rectangleguillotine hard-codes it as the
# column-generation LP solver (`column_generation_strips.hpp`,
# `linear_programming_solver_name = SolverName::CLP`), and column generation is
# auto-enabled for exactly the repetitive bin-packing instances this product
# sends. So install Debian's arm64 CoinOR static libraries and lay them out the
# way mathoptsolverscmake expects the release tarballs — `<dir>/include` holding
# `coin/`, `<dir>/lib/lib{CoinUtils,Clp,OsiClp}.a` — for the
# FETCHCONTENT_SOURCE_DIR_* overrides passed at configure time. amd64 (CI, prod)
# is untouched and keeps using the pinned upstream archives.
RUN if [ "$TARGETARCH" = "arm64" ]; then \
        apt-get update \
        && apt-get install -y --no-install-recommends \
             coinor-libcoinutils-dev coinor-libosi-dev coinor-libclp-dev \
        && rm -rf /var/lib/apt/lists/* \
        && mkdir -p /opt/coinor/lib \
        && ln -s /usr/include /opt/coinor/include \
        && for lib in CoinUtils Clp OsiClp; do \
               ln -s "/usr/lib/$(gcc -dumpmachine)/lib${lib}.a" "/opt/coinor/lib/lib${lib}.a"; \
           done; \
    fi

# cmake via pip rather than apt — apt's cmake on python:3.12-slim (Debian
# bookworm) is older than PackingSolver's CMakeLists.txt requires.
RUN pip install --no-cache-dir cmake==4.0.3

WORKDIR /usr/src/packingsolver

# Download the fixed source archive and verify its checksum before extracting
# — the archive is untrusted until the hash matches exactly.
RUN curl -fsSL -o packingsolver.tar.gz \
      "https://github.com/fontanf/packingsolver/archive/${PACKINGSOLVER_COMMIT}.tar.gz" \
    && echo "${PACKINGSOLVER_SHA256}  packingsolver.tar.gz" | sha256sum --check --status \
    && tar -xzf packingsolver.tar.gz --strip-components=1 \
    && rm packingsolver.tar.gz

# Configure Release, unit tests off, and build ONLY the rectangleguillotine
# main target — the other packing types (rectangle, boxstacks, irregular, ...)
# are never compiled. CMake's FetchContent pulls Boost/HiGHS/treesearchsolver
# etc. at configure/build time, hence `git`/`curl`/`ca-certificates` above.
RUN set -eu; \
    coinor_override=""; \
    if [ -d /opt/coinor ]; then \
        coinor_override="-DFETCHCONTENT_SOURCE_DIR_COINUTILS=/opt/coinor -DFETCHCONTENT_SOURCE_DIR_CLP=/opt/coinor"; \
    fi; \
    cmake -S . -B build \
      -DCMAKE_BUILD_TYPE=Release \
      -DPACKINGSOLVER_BUILD_TEST=OFF \
      $coinor_override \
    && cmake --build build --target PackingSolver_rectangleguillotine_main --parallel "$(nproc)"

# Install manually rather than `cmake --install` — only one target was built,
# and the project's install rules cover every packing-type executable.
RUN mkdir -p /opt/packingsolver/bin \
    && cp build/src/rectangleguillotine/packingsolver_rectangleguillotine \
         /opt/packingsolver/bin/packingsolver_rectangleguillotine \
    && strip /opt/packingsolver/bin/packingsolver_rectangleguillotine

# --- builder: resolve & install deps into the system interpreter -------------
FROM python:3.12-slim AS builder

COPY --from=ghcr.io/astral-sh/uv:0.8.22 /uv /uvx /bin/

# Deps go into the system interpreter (/usr/local), not a .venv under /app —
# the container is the isolation. Keeping site-packages out of /app means the
# dev source bind-mount (deploy/compose.yaml) can never shadow installed
# dependencies, so no venv-preserving volume is needed.
ENV UV_PROJECT_ENVIRONMENT=/usr/local \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends ca-certificates git \
    && rm -rf /var/lib/apt/lists/*

# Deps only — the project is `package = false`, so nothing of it is installed.
RUN --mount=type=cache,target=/root/.cache/uv \
    --mount=type=bind,source=pyproject.toml,target=pyproject.toml \
    --mount=type=bind,source=uv.lock,target=uv.lock \
    uv sync --frozen --no-install-project --no-dev

COPY . /app

# --- runtime -----------------------------------------------------------------
FROM python:3.12-slim AS runtime

# Shared-library runtime deps for the PackingSolver executable only — no
# compiler, no headers, no CMake cache, no PackingSolver source (those stay in
# packingsolver-builder and are discarded with it).
RUN apt-get update \
    && apt-get install -y --no-install-recommends liblapack3 libbz2-1.0 libgomp1 \
    && rm -rf /var/lib/apt/lists/*

RUN useradd --create-home --uid 1000 app
WORKDIR /app

# Same base image, so overlaying /usr/local transplants site-packages and the
# console scripts (uvicorn, fastapi, alembic) verbatim; they're on PATH already.
COPY --from=builder /usr/local /usr/local
COPY --from=builder --chown=app:app /app /app

# The pinned PackingSolver executable cutting-engine's packingsolver provider
# resolves via `shutil.which` (PACKINGSOLVER_PROVIDER_SPEC.md, "Executable
# resolution") — root-owned, mode 0755, next to the other console scripts on
# PATH. The application process itself stays non-root (`USER app` below).
COPY --from=packingsolver-builder \
     /opt/packingsolver/bin/packingsolver_rectangleguillotine \
     /usr/local/bin/packingsolver_rectangleguillotine
RUN chown root:root /usr/local/bin/packingsolver_rectangleguillotine \
    && chmod 0755 /usr/local/bin/packingsolver_rectangleguillotine

# MIT license notice for the vendored executable (THIRD_PARTY_NOTICES.md at
# the repo root carries the same text for the product as a whole).
COPY --from=packingsolver-builder \
     /usr/src/packingsolver/LICENSE \
     /usr/share/licenses/packingsolver/LICENSE

# Build-time smoke test: every shared library must resolve (no "not found"),
# and the executable must actually run. This pinned build has no long
# `--help` option at all — passing it is itself an "unrecognised option"
# error. The real help text comes from `-h` (or no arguments), still exit
# code 1: PackingSolver's argument parser treats printing usage as a
# failure regardless of how it was invoked. Verified by hand against the
# pinned commit's binary before writing this assertion (see
# PACKINGSOLVER_PROVIDER_SPEC.md, "Packing and deployment" for the spec's
# original, older-pin assumption of `--help`).
RUN ldd /usr/local/bin/packingsolver_rectangleguillotine \
    && ! ldd /usr/local/bin/packingsolver_rectangleguillotine | grep -q "not found"
RUN help_output="$(/usr/local/bin/packingsolver_rectangleguillotine -h)"; rc=$?; \
    if [ "$rc" -ne 1 ]; then \
        echo "expected exit code 1 from -h, got $rc" >&2; exit 1; \
    fi; \
    echo "$help_output" | grep -q "Allowed options" || { \
        echo "expected 'Allowed options' in -h output" >&2; exit 1; \
    }

ENV PYTHONUNBUFFERED=1

USER app
EXPOSE 8000

# Run migrations then start the server. Override CMD in compose for dev.
CMD ["sh", "-c", "alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port 8000"]
