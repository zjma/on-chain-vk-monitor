from flask import Flask, request, redirect, render_template_string


app = Flask(__name__)


text = '''
{
    "type": "0x1::keyless_account::Configuration",
    "data": {
        "max_commited_epk_bytes": 93,
        "max_exp_horizon_secs": "10000000",
        "max_extra_field_bytes": 350,
        "max_iss_val_bytes": 120,
        "max_jwt_header_b64_bytes": 300,
        "max_signatures_per_txn": 3,
        "override_aud_vals": [
            "test.recovery.aud"
        ],
        "training_wheels_pubkey": {
            "vec": [
                "__CHANGE_THIS__"
            ]
        }
    }
}
'''


@app.route("/")
def index():
    return app.response_class(
        response=text,
        status=200,
        mimetype='application/json'
    )


@app.route("/edit", methods=["GET", "POST"])
def edit():
    global text
    if request.method == "POST":
        new_text = request.form["content"]
        if len(new_text) < 4096:
            text = new_text
        return redirect("/")

    return render_template_string("""
        <h1>Edit Text</h1>
        <form method="post">
            <textarea name="content" rows="20" cols="80">{{ content }}</textarea><br>
            <input type="submit" value="Save">
        </form>
    """, content=text)


if __name__ == "__main__":
    app.run(debug=True, host='::', port=8080)
