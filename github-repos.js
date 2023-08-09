document.addEventListener('DOMContentLoaded', function () {
    fetch('https://api.github.com/users/corazza/repos?sort=pushed&direction=desc&per_page=100')
        .then(response => response.json())
        .then(data => {
            let output = '<h3>My projects</h3>';
            const excludedRepos = ["corazza.github.io", "pmf-materijali", "pytorch"];
            const priorityRepos = [
                "text2task",
                "stochastic-reward-machines",
                "snaskell",
                "game-idris",
                "min-cost-flow-minimum-quantities",
                "vision-transformer-quantization",
                "pose",
                "EfficientCNN"];

            // Filter out the excluded repos
            data = data.filter(repo => !excludedRepos.includes(repo.name));

            // Sort the data
            data.sort((a, b) => {
                if (priorityRepos.includes(a.name) && priorityRepos.includes(b.name)) {
                    return priorityRepos.indexOf(a.name) - priorityRepos.indexOf(b.name);
                } else if (priorityRepos.includes(a.name)) {
                    return -1;
                } else if (priorityRepos.includes(b.name)) {
                    return 1;
                } else {
                    return new Date(b.pushed_at) - new Date(a.pushed_at);
                }
            });

            data.forEach(repo => {
                output += `
                <article class="repo-card">
                    <h4><a href="${repo.html_url}" target="_blank">${repo.name}</a></h4>
                    <p>${repo.description ? repo.description : 'No description provided.'}</p>
                    <footer>
                        <span class="language">${repo.language ? repo.language : 'Unknown'}</span>
                        <span class="stars">⭐ ${repo.stargazers_count}</span>
                    </footer>
                </article>`;
            });

            document.getElementById('github-repos').innerHTML = output;
        })
        .catch(error => console.error('Error fetching GitHub repos:', error));
});
