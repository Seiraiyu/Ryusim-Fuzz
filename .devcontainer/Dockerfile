FROM ghcr.io/seiraiyu/ryusim-fuzz:latest

ARG REMOTE_USER=vscode
ARG REMOTE_UID=1000
ARG REMOTE_GID=1000

# Create non-root user
RUN groupadd --gid ${REMOTE_GID} ${REMOTE_USER} && \
    useradd --uid ${REMOTE_UID} --gid ${REMOTE_GID} -m -s /bin/bash ${REMOTE_USER} && \
    echo "${REMOTE_USER} ALL=(ALL) NOPASSWD:ALL" >> /etc/sudoers

# Node.js (needed for Claude Code)
RUN curl -fsSL https://deb.nodesource.com/setup_22.x | bash - && \
    apt-get install -y nodejs && \
    rm -rf /var/lib/apt/lists/*

# Persist bash history
RUN SNIPPET="export PROMPT_COMMAND='history -a' && export HISTFILE=/commandhistory/.bash_history" \
    && mkdir /commandhistory \
    && touch /commandhistory/.bash_history \
    && chown -R ${REMOTE_USER} /commandhistory

# Create workspace and config directories
RUN mkdir -p /workspace /home/${REMOTE_USER}/.claude && \
    chown -R ${REMOTE_USER}:${REMOTE_USER} /workspace /home/${REMOTE_USER}/.claude

USER ${REMOTE_USER}

# Claude Code CLI
RUN curl -fsSL https://claude.ai/install.sh | bash

ENV PATH="/home/${REMOTE_USER}/.local/bin:$PATH"
ENV HOME=/home/${REMOTE_USER}
