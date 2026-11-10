document.querySelectorAll('[data-reference-dialog]').forEach((button) => {
    button.addEventListener('click', () => {
        const dialog = document.getElementById(button.dataset.referenceDialog);
        if (dialog instanceof HTMLDialogElement) {
            dialog.showModal();
        }
    });
});

const substanceInput = document.getElementById('substance-search');
const suggestionList = document.getElementById('substance-suggestions');
const searchStatus = document.getElementById('substance-search-status');

if (substanceInput && suggestionList && searchStatus) {
    let debounceTimer;
    let controller;
    let requestVersion = 0;
    let activeIndex = -1;
    let matches = [];

    const showStatus = (message) => {
        searchStatus.textContent = message;
        searchStatus.hidden = !message;
    };

    const closeSuggestions = () => {
        requestVersion += 1;
        clearTimeout(debounceTimer);
        controller?.abort();
        matches = [];
        activeIndex = -1;
        suggestionList.replaceChildren();
        suggestionList.hidden = true;
        substanceInput.setAttribute('aria-expanded', 'false');
        substanceInput.removeAttribute('aria-activedescendant');
        showStatus('');
    };

    const selectMatch = (index) => {
        const match = matches[index];
        if (!match) return;
        const destination = new URL(substanceInput.dataset.suggestionsUrl, location.origin);
        destination.searchParams.set('compound', String(match.cid));
        location.assign(destination);
    };

    const activate = (index) => {
        activeIndex = index;
        Array.from(suggestionList.children).forEach((option, position) => {
            option.setAttribute('aria-selected', String(position === index));
        });
        const option = suggestionList.children[index];
        substanceInput.setAttribute('aria-activedescendant', option.id);
        option.scrollIntoView({ block: 'nearest' });
    };

    const scheduleSearch = () => {
        closeSuggestions();
        const query = substanceInput.value.trim();
        if (query.length < 2) return;
        const version = requestVersion;
        debounceTimer = setTimeout(async () => {
            controller = new AbortController();
            showStatus('Searching...');
            const url = new URL(substanceInput.dataset.suggestionsUrl, location.origin);
            url.searchParams.set('suggest', '1');
            url.searchParams.set('q', query);
            try {
                const response = await fetch(url, {
                    signal: controller.signal,
                    headers: { Accept: 'application/json' },
                });
                if (!response.ok || response.redirected) throw new Error('Search unavailable');
                const payload = await response.json();
                if (version !== requestVersion) return;
                matches = payload.results;
                matches.forEach((match, index) => {
                    const option = document.createElement('li');
                    option.id = `substance-match-${match.cid}`;
                    option.setAttribute('role', 'option');
                    option.setAttribute('aria-selected', 'false');
                    const name = document.createElement('strong');
                    name.textContent = match.name;
                    const identifiers = document.createElement('span');
                    identifiers.textContent = `CID ${match.cid}${match.cas_numbers.length ? ` · CAS ${match.cas_numbers.join(', ')}` : ''}`;
                    option.append(name, identifiers);
                    option.addEventListener('pointerdown', (event) => event.preventDefault());
                    option.addEventListener('click', () => selectMatch(index));
                    suggestionList.append(option);
                });
                suggestionList.hidden = matches.length === 0;
                substanceInput.setAttribute('aria-expanded', String(matches.length > 0));
                showStatus(matches.length
                    ? `${matches.length} matches${payload.more ? '; more available' : ''}.`
                    : 'No matching substances.');
            } catch (error) {
                if (error.name !== 'AbortError' && version === requestVersion) {
                    showStatus('Suggestions unavailable. Use Search to continue.');
                }
            }
        }, 200);
    };

    substanceInput.addEventListener('input', scheduleSearch);
    substanceInput.addEventListener('focus', scheduleSearch);
    substanceInput.addEventListener('keydown', (event) => {
        if (event.key === 'Escape') {
            event.preventDefault();
            closeSuggestions();
        } else if (matches.length && ['ArrowDown', 'ArrowUp'].includes(event.key)) {
            event.preventDefault();
            const next = event.key === 'ArrowDown'
                ? (activeIndex + 1) % matches.length
                : (activeIndex < 0 ? matches.length - 1 : (activeIndex - 1 + matches.length) % matches.length);
            activate(next);
        } else if (event.key === 'Enter' && activeIndex >= 0) {
            event.preventDefault();
            selectMatch(activeIndex);
        }
    });
    substanceInput.addEventListener('blur', closeSuggestions);
    document.addEventListener('pointerdown', (event) => {
        if (!substanceInput.closest('.removal-autocomplete').contains(event.target)) {
            closeSuggestions();
        }
    });
}