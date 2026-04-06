FROM ghcr.io/seiraiyu/ryusim-fuzz:latest

ARG REMOTE_USER=vscode
ARG REMOTE_UID=1000
ARG REMOTE_GID=1000

# Remove existing user/group with conflicting IDs
RUN if getent passwd ${REMOTE_UID} >/dev/null 2>&1; then \
        existing_user=$(getent passwd ${REMOTE_UID} | cut -d: -f1); \
        userdel -r ${existing_user} 2>/dev/null || userdel ${existing_user}; \
    fi && \
    if getent group ${REMOTE_GID} >/dev/null 2>&1; then \
        existing_group=$(getent group ${REMOTE_GID} | cut -d: -f1); \
        groupdel ${existing_group} 2>/dev/null || true; \
    fi

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
