const supabase = supabase.createClient('{{ url_provided }}', '{{ key_provided }}');

    async function login() {
        const email = document.getElementById('email').value;
        const password = document.getElementById('password').value;

        const { data, error } = await supabase.auth.signInWithPassword({ email, password });

        if (error) {
            alert("Erreur: " + error.message);
        } else {
            // On stocke le jeton (access_token) dans un cookie pour que Flask le voie
            document.cookie = "supabase_token=" + data.session.access_token + "; path=/; max-age=3600";
            window.location.href = "/admin";
        }
    }