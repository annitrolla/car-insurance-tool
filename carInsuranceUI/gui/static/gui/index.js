$('#upload-btn').on( 'click', function (e) {
    var cookie = getCookie('csrftoken'); 
    var files = document.getElementById('file-input').files;
    var formdata = new FormData(files[0]);
    
    console.log(files);
    $.ajax({
        url: "recognize_car_plate",
        method: 'POST',
        data:{'video': formdata},
        headers: {'X-CSRFToken': cookie},
        success: function(response){
            alert(response);
        }
    });
} );

function getCookie(name) {
    var cookieValue = null;
    if (document.cookie && document.cookie !== '') {
        var cookies = document.cookie.split(';');
        for (var i = 0; i < cookies.length; i++) {
            var cookie = jQuery.trim(cookies[i]);
            // Does this cookie string begin with the name we want?
            if (cookie.substring(0, name.length + 1) === (name + '=')) {
                cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
                break;
            }
        }
    }
    return cookieValue;
}

