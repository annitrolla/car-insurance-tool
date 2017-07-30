var ajaxXhr;

$('#upload-btn').on( 'click', function (e) {
    var cookie = getCookie('csrftoken'); 
    var files = document.getElementById('file-input').files;
    var formdata = new FormData();
    formdata.append('video', $("#file-input")[0].files[0]);
    
    $('body').css('cursor', 'progress');
    
    ajaxXhr = $.ajax({
        url: "recognize_car_plate",
        type: 'POST',
        processData: false,
        contentType: false,
        data: formdata,
        dataType: 'html',
        headers: {'X-CSRFToken': cookie},
        success: function(response){
            $('#results-div').html(response);
            $('body').css('cursor', 'auto');
        },
        error: function(response){
            $('body').css('cursor', 'auto');
        }
    });
} );

$('#cancel-btn').click(function(event) {
    ajaxXhr.abort()
});

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

// "Choose a file" button will change its name to name of the file
var inputs = document.querySelectorAll( '#file-input' );
Array.prototype.forEach.call( inputs, function( input )
{
    var label    = input.nextElementSibling,
        labelVal = label.innerHTML;

    input.addEventListener( 'change', function( e )
    {
        var fileName = '';
        if( this.files && this.files.length > 1 )
            fileName = ( this.getAttribute( 'data-multiple-caption' ) || '' ).replace( '{count}', this.files.length );
        else
            fileName = e.target.value.split( '\\' ).pop();

        if( fileName )
            label.querySelector( 'span' ).innerHTML = fileName;
        else
            label.innerHTML = labelVal;
    });
});