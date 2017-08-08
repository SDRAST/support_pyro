var util = {
    requestData: function(route, args, kwargs, callbacks){
        $.ajax({
            type:"GET",
            data:JSON.stringify({'args':args,'kwargs':kwargs}),
            // data:JSON.stringify([args,kwargs]),
            url: $SCRIPT_ROOT+route,
            success: function(msg){
                var data = msg.data;
                callbacks.forEach(function(callback){
                    callback(data) ;
                })
            },
            failure: function(msg){
                console.log("Failure message from server: "+msg);
            }
        });
    },

}

function App(){

    this.init = function(){
        this.setStatus(this)("Howdy there!") ;
        $('#mySpinbox').spinbox({
    	    value: 1,
    	    min: 1,
    	    max: 10000,
    	    step: 1,
    	    decimalMark: '.',
    	});
        $("#arg-up").on('click', this.square(this))
        $("#arg-down").on('click', this.square(this))
    }

    this.setStatus = function(self){
        return function(msg){
            $("#status-bar").html("<h4>{}</h4>".format(msg)) ;
        }
    }

    this.square = function(self){
        return function(){
            var arg = $('#mySpinbox').spinbox('getValue')
            util.requestData("square", [arg], {},[self.square_cb(self)]);
        }
    }

    this.square_cb = function(self){
        return function(data){
            result = data.result;
            status = data.status;
            if (result){
                $("#result").html("<h4>{}</h4>".format(result));
            }
            self.setStatus(self)(status);
        }
    }
}

$(document).ready(function(){
    var app = new App();
    app.init();
});
