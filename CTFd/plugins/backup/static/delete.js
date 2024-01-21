function htmlentities(str) {
    return String(str).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
}

$(".delete-backup").click(function (e) {
    e.preventDefault();
    let filename = $(this).attr("data-filename");


    CTFd.ui.ezq.ezQuery({
        title: "Delete Backup",
        body: `Are you sure you want to delete ${filename}?`,
        success: async function () {
            let response = await CTFd.fetch(`/plugins/backup/admin/delete?name=${filename}`, {
                method: "GET"
            })
            response = await response.json()
            if (response.success === true){
                window.location.reload()
            }else{
                CTFd.ui.ezq.ezToast({
                    title: "Error!",
                    body: "Delete Backup Failed!"
                });
            }
        }
    });
});

$(".backup-now").click(async function (e) {
    e.preventDefault();
    let response = await CTFd.fetch(`/plugins/backup/admin/backupNow`, {
        method: "GET"
    })
    response = await response.json()
    if (response.success === true) {
        window.location.reload()
    } else {
        CTFd.ui.ezq.ezToast({
            title: "Error!",
            body: "Backup Failed!",
        });
    }
});