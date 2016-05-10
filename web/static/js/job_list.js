
var dropped_files = [];

// function hideUploadOverlay()
// {
//     document.getElementById("upload_overlay").style.display = "none";
//     document.getElementsByName("ped_upload_form")[0].reset();
//     document.getElementsByName("ped_file_upload_progress")[0].value = 0;
// }

function fileSelected()
{
    var file = document.getElementsByName("ped_file")[0].files[0];
    if (file)
    {
        var fileSize = 0;
        if (file.size > 1024 * 1024)
            fileSize = (Math.round(file.size * 100 / (1024 * 1024)) / 100).toString() + "MB";
        else
            fileSize = (Math.round(file.size * 100 / 1024) / 100).toString() + "KB";

        document.getElementsByName("ped_filename")[0].value = file.name;
        //document.getElementById("fileSize").innerHTML = "Size: " + fileSize;
        //document.getElementById("fileType").innerHTML = "Type: " + file.type;
    }
    else
    {
        document.getElementsByName("ped_filename")[0].value = "";
    }
}



function bindTableRows()
{
    var table_rows = document.getElementById("jobs_table").getElementsByTagName("tr");
    for (var i = 0; i < table_rows.length; ++i)
    {
        if (table_rows[i].hasAttribute("data-id"))
        {
            var r = table_rows[i];
            (function (row_element)
            {
                row_element.addEventListener("click", function (ev)
                {
                    var job_id = row_element.getAttribute("data-id");
                    window.location = "/jobs/" + job_id;
                });
            })(r);
        }
    }
}

function fetchJobs()
{
    var xhr = new XMLHttpRequest();
    xhr.addEventListener("load", function(ev)
    {
        var jobs = JSON.parse(xhr.responseText);

        var jobs_table = document.getElementById("jobs_table");
        jobs_table.innerHTML = ejs.render(document.getElementById("table_row_tmpl").innerText, {"jobs" : jobs });
        bindTableRows();
    }, false);

    xhr.addEventListener("error", uploadFailed, false);
    xhr.addEventListener("abort", uploadCanceled, false);
    xhr.open("GET", "/api/jobs");
    xhr.send();
}


function setProgressBarValue(progress)
{
    //document.getElementsByName("ped_file_upload_progress")[0].value = progress.toString();
    $(".ubox-progress").css("width", progress.toString() + "%");
}

function uploadProgress(evt)
{
    if (evt.lengthComputable)
    {
        var percentComplete = Math.round(evt.loaded * 100 / evt.total);
        setProgressBarValue(percentComplete);
    }
    else
    {
        //document.getElementById("progressNumber").innerHTML = "unable to compute";
    }
}

function uploadFailed(evt)
{
    alert("There was an error attempting to upload the file.");
    setProgressBarValue(0);
}

function uploadCanceled(evt)
{
    alert("The upload has been canceled by the user or the browser dropped the connection.");
    setProgressBarValue(0);
}

function uploadFile()
{
    //$("[name=ped_filename],[name=job_name]").removeClass("error");
    //var job_name = document.getElementsByName("job_name")[0].value;
    //if (document.getElementsByName("ped_file")[0].files.length !== 1 || !job_name)
    //{
    //    if (document.getElementsByName("ped_file")[0].files.length < 1)
    //        $("[name=ped_filename]").addClass("error");
    //    if (!job_name)
    //        $("[name=job_name]").addClass("error");
    //}
    //else
    {
        $(".ubox-button").prop("disabled", true);
        var fd = new FormData();
        fd.append("ped_file", dropped_files[0]); //document.getElementsByName("ped_file")[0].files[0]);
        fd.append("job_name", dropped_files[0].name);
        var xhr = new XMLHttpRequest();
        xhr.upload.addEventListener("progress", uploadProgress, false);
        xhr.addEventListener("load", function (evt)
        {
            /* This event is raised when the server send back a response */
            if (xhr.status >= 200 && xhr.status < 300)
            {
                fetchJobs();
            }
            else
            {
                try
                {
                    resp = JSON.parse(xhr.responseText);
                    alert(resp.error);
                }
                catch (ex)
                {
                    alert(xhr.statusText);
                }
            }
            dropped_files = [];
            $(".ubox-button").hide();
            setProgressBarValue(0);
            $(".ubox-button").prop("disabled", false);
        }, false);
        xhr.addEventListener("error", uploadFailed, false);
        xhr.addEventListener("abort", uploadCanceled, false);
        xhr.open("POST", "/api/jobs");
        xhr.send(fd);
    }
}



document.onreadystatechange = function()
{
    if (document.readyState === "complete")
    {
        fetchJobs();
        // document.getElementsByName("ped_upload_form")[0].addEventListener("submit", function(ev)
        // {
        //     ev.preventDefault();
        //     uploadFile();
        // });

        document.getElementById("create_job_button").addEventListener("click", function(ev)
        {
            $("form.ubox [name=ped_file]")[0].click();
        });

        // document.getElementById("upload_overlay").addEventListener("click", function(ev)
        // {
        //     hideUploadOverlay();
        // });

        // document.getElementsByName("ped_upload_form")[0].addEventListener("click", function(ev)
        // {
        //     ev.stopPropagation();
        // });

        // document.getElementsByName("ped_filename")[0].addEventListener("click", function(ev)
        // {
        //     document.getElementsByName("ped_file")[0].click();
        // });

        // document.getElementsByName("ped_file")[0].addEventListener("change", function(ev)
        // {
        //     fileSelected();
        // });

        // document.addEventListener("keyup", function(e)
        // {
        //     if (e.keyCode == 27) // ESC
        //     {
        //         hideUploadOverlay();
        //     }
        // });


        var has_modern_upload = function() {
            var div = document.createElement('div');
            return (('draggable' in div) || ('ondragstart' in div && 'ondrop' in div)) && 'FormData' in window && 'FileReader' in window;
        }();

        if (!has_modern_upload)
        {
            alert("Browser not supported");
        }
        else
        {
            var ubox_form = $('form.ubox');
            ubox_form.on('drag dragstart dragend dragover dragenter dragleave drop', function(e)
            {
                e.preventDefault();
                e.stopPropagation();
            })
            .on('dragover dragenter', function()
            {
                ubox_form.addClass('is-dragged-over');
            })
            .on('dragleave dragend drop', function()
            {
                ubox_form.removeClass('is-dragged-over');
            })
            .on('drop', function(e)
            {
                if (e.originalEvent.dataTransfer.items.length) // TODO: Filter directory.
                    dropped_files = e.originalEvent.dataTransfer.files;
                else
                    dropped_files = [];

                if (dropped_files.length)
                    $(".ubox-button").show().text("Create Job (" + dropped_files[0].name + ")");
                else
                {
                    $(".ubox-button").hide();
                }
            });

            var file_input = $("form.ubox [name=ped_file]")[0];
            $(file_input).on("change", function()
            {
                dropped_files = file_input.files || [];
                if (dropped_files.length)
                    $(".ubox-button").show();
                else
                    $(".ubox-button").hide();
            });

            ubox_form.find("button[name=upload]").on("click", function(e)
            {
                uploadFile();
            });
        }

    }
};