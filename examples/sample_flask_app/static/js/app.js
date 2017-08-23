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
    makeSpinBox: function(bindElement, id, cb){
        $(bindElement).prepend(function(){
            return $(`
            <div class="spinbox" data-initialize="spinbox" id="{}">
            <input type='text' class='form-control input-mini spinbox-input'>
                <div class='spinbox-buttons btn-group btn-group-vertical'>
                    <button type='button' class='btn btn-default spinbox-up btn-xs' id='arg-up'>
                        <span class='glyphicon glyphicon-chevron-up'></span><span class='sr-only'>Increase</span>
                    </button>
                    <button type='button' class='btn btn-default spinbox-down btn-xs' id='arg-down'>
                        <span class='glyphicon glyphicon-chevron-down'></span><span class='sr-only'>Decrease</span>
                    </button>
                </div>
            </div>`.format(id)).on('click', cb)
        });
    }
}

function App(){

    this.init = function(){
        this.setStatus(this)("Howdy there!") ;
        util.makeSpinBox("#spinBoxRow","mySpinbox",this.square(this),{step:10.0});
        $("#mySpinbox").spinbox({step:10.0});
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
